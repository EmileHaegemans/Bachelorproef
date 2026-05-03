"""
ELF symbol -> page mapping helpers.

Loads the .symtab / .dynsym sections of an enclave binary and groups
every symbol by the 4 KiB page it lives on. The resulting map can be
attached to TraceData.symbol_map and used to look up pages by symbol
name (handy when page numbers shift between rebuilds of the enclave).
"""

from __future__ import annotations

from typing import Dict, List, Tuple, TYPE_CHECKING
from elftools.elf.elffile import ELFFile

if TYPE_CHECKING:
    from .model import TraceData


def get_symbol_map(elf_path: str) -> Dict[str, str]:
    """
    Read an ELF file and return a page_name -> symbols map.

    Iterates the .symtab and .dynsym sections, divides each non-zero
    symbol address by 4096 (the page size), and groups symbols by the
    resulting page index. Multiple symbols on the same page are joined
    with ", ".

    @param elf_path path to the enclave's ELF binary
    @return mapping like {"_17": "modpow@0x11000, ..."}; empty on error
    """
    mapping: Dict[str, str] = {}
    
    try:
        with open(elf_path, "rb") as f:
            elf = ELFFile(f)

            symbol_sections = [
                elf.get_section_by_name(".symtab"),
                elf.get_section_by_name(".dynsym")
            ]

            for section in symbol_sections:
                if not section:
                    continue
                
                symbols = sorted(section.iter_symbols(), key=lambda s: s["st_value"])
                
                for symbol in symbols:
                    st_type = symbol["st_info"]["type"]
                    if st_type in ("STT_FUNC", "STT_NOTYPE", "STT_OBJECT") and symbol["st_value"] != 0:
                        
                        addr = symbol["st_value"]
                        page_idx = addr // 4096
                        page_name = f"_{page_idx}"
                        
                        entry = f"{symbol.name}@0x{addr:x}"
                        
                        if page_name in mapping:
                            if entry not in mapping[page_name]:
                                mapping[page_name] += f", {entry}"
                        else:
                            mapping[page_name] = entry

            return mapping
            
    except Exception as e:
        print(f"Error reading symbols from {elf_path}: {e}")
        return {}


def get_symbols_for_page(trace: TraceData, page: str) -> List[str]:
    """
    Return every symbol mapped to a specific page.

    @param trace the TraceData carrying a populated symbol_map
    @param page the canonical page name (e.g. "_17")
    @return list of "name@0xaddr" strings; empty if the page is unknown
    """
    symbols_str = trace.symbol_map.get(page, "")
    if not symbols_str:
        return []
    return [s.strip() for s in symbols_str.split(",")]


def find_pages_for_symbol(trace: TraceData, pattern: str) -> List[Tuple[str, str]]:
    """
    Find every (page, symbol) pair whose symbol name matches a substring.

    Matching is case-insensitive.

    @param trace the TraceData carrying a populated symbol_map
    @param pattern substring to search for inside symbol names
    @return list of (page_name, full_symbol_string) matches
    """
    results = []
    pattern = pattern.lower()
    for page, symbols_str in trace.symbol_map.items():
        sym_list = [s.strip() for s in symbols_str.split(",")]
        for s in sym_list:
            if pattern in s.lower():
                results.append((page, s))
    return results


def find_page_by_exact_symbol(trace: TraceData, symbol_name: str) -> str | None:
    """
    Resolve the page hosting a symbol by exact name match.

    Useful when several symbols share a page or have similar names and
    the substring search of find_pages_for_symbol would be ambiguous.

    @param trace the TraceData carrying a populated symbol_map
    @param symbol_name the exact symbol name (without "@0x..." suffix)
    @return the canonical page name (e.g. "_17"), or None if not found
    """
    pattern = f"{symbol_name}@"
    for page, symbols_str in trace.symbol_map.items():
        sym_list = [s.strip() for s in symbols_str.split(",")]
        if any(s.startswith(pattern) for s in sym_list):
            return page
    return None
