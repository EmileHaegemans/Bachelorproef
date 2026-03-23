from __future__ import annotations

from typing import Dict, List, Tuple, TYPE_CHECKING
from elftools.elf.elffile import ELFFile

if TYPE_CHECKING:
    from .model import TraceData


def get_symbol_map(elf_path: str) -> Dict[str, str]:
    """
    Reads an ELF file and returns a mapping of page names (e.g., '_17')
    to the function symbols (headers) found at those addresses.
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
                    if st_type in ("STT_FUNC", "STT_NOTYPE") and symbol["st_value"] != 0:
                        
                        addr = symbol["st_value"]
                        page_idx_hex = addr // 4096
                        page_name = f"_{hex(page_idx_hex)[2:]}"
                        
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
    """Returns all symbols mapped to a specific page."""
    symbols_str = trace.symbol_map.get(page, "")
    if not symbols_str:
        return []
    return [s.strip() for s in symbols_str.split(",")]


def find_pages_for_symbol(trace: TraceData, pattern: str) -> List[Tuple[str, str]]:
    """
    Returns a list of (page, full_symbol_name) for symbols matching the pattern.
    """
    results = []
    pattern = pattern.lower()
    for page, symbols_str in trace.symbol_map.items():
        sym_list = [s.strip() for s in symbols_str.split(",")]
        for s in sym_list:
            if pattern in s.lower():
                results.append((page, s))
    return results
