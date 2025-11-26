# ook mogelijk met echte rsa maar moeilijk om te volgen 
# import rsa

#Ai rsa met trace aan teogevoegd 

def debug_pow(a, b, n, state):
    
    res = 1
    state["trace"] = []  
    for bit in bin(b)[2:]:
        
    
        res = (res * res) % n
        state["trace"].append(("square", res, bit))

        if bit == "1":
            res = (res * a) % n
            state["trace"].append(("multiply", res, bit))

    return res




def init_toy_rsa_trace(state):
    #zelf init voor te volgen 
    n = 3233     
    e = 17       
    d = 2753     

    
    message_int = 65  

    cipher_int = pow(message_int, e, n)

    pow_state = {"trace": []}
    decoded_int = debug_pow(cipher_int, d, n, pow_state)

    state["rsa_trace"] = pow_state["trace"]
    state["trace_index"] = -1  
    state["registers"] = {
        "message_int": message_int,
        "cipher_int": cipher_int,
        "exp_e": e,
        "exp_d": d,
        "mod_n": n,
        "step": -1,
        "op": None,
        "bit": None,
        "res": 1,
        "decoded_int": decoded_int,
    }

# test

#Optionele met import rsa voor praktijk mogelijke rsa 

# def init_rsa_trace_with_library(state):
#     """
#     Same idea as init_toy_rsa_trace, but using the 'rsa' library to
#     generate a real key and ciphertext. Numbers will be much bigger.
#     """
#     # Generate a (still small-ish) key – you can change 256/512/etc.
#     pubkey, privkey = rsa.newkeys(256)
#     message = b"hello"
#
#     cipher_bytes = rsa.encrypt(message, pubkey)
#     cipher_int = int.from_bytes(cipher_bytes, "big")
#
#     d = privkey.d
#     n = privkey.n
#
#     pow_state = {"trace": []}
#     decoded_int = debug_pow(cipher_int, d, n, pow_state)
#
#     state["rsa_trace"] = pow_state["trace"]
#     state["trace_index"] = -1
#     state["registers"] = {
#         "message_bytes": message,
#         "cipher_int": cipher_int,
#         "exp_e": pubkey.e,
#         "exp_d": d,
#         "mod_n": n,
#         "step": -1,
#         "op": None,
#         "bit": None,
#         "res": 1,
#         "decoded_int": decoded_int,
#     }




def print_help():
    print("""
Available commands:
  help
  quit
  page-step          # do 4 steps at once 
  single-step        # do 1 step of modular exponentiation
  break <step>       # set breakpoint on a step index
  unbreak <step>     # remove breakpoint
  breakpoints        # list breakpoints
  registers          # show current 'registers'
""")


def do_single_step(state):
    trace = state.get("rsa_trace", [])
    if not trace:
        print("[single-step] No RSA trace available.")
        return False 

    idx = state.get("trace_index", -1) + 1
    if idx >= len(trace):
        print("[single-step] No more steps, computation finished.")
        return False 

    op, res, bit = trace[idx]
    state["trace_index"] = idx
    state["registers"]["step"] = idx
    state["registers"]["op"] = op
    state["registers"]["bit"] = bit
    state["registers"]["res"] = res

    
    if str(idx) in state["breakpoints"]:
        print(f"[breakpoint] Hit at step {idx}")

    print(f"[single-step] step {idx}: op={op}, bit={bit}, res={res}")

    if str(idx) in state["breakpoints"]:
        print(f"[breakpoint] Hit at step {idx}")
        return True 


def page_step_command(state, page_size=4):
    print(f"[page-step] Executing up to {page_size} steps...")
    for _ in range(page_size):
        before = state.get("trace_index", -1)
        br = do_single_step(state)

        if br:
            print("[page-step] Stopped on breakpoint.")
            break

        after = state.get("trace_index", -1)
        if after == before:
            break


def single_step_command(state):
    do_single_step(state)


def break_command(step, state):
    state["breakpoints"].add(step)
    print("Breakpoint set on step", step)


def unbreak_command(step, state):
    if step in state["breakpoints"]:
        state["breakpoints"].remove(step)
        print("Breakpoint removed from step", step)
    else:
        print("No breakpoint set on step", step)


def show_breakpoints(state):
    if len(state["breakpoints"]) == 0:
        print("no breakpoint set.")
    else:
        print("Breakpoints:")
        for point in sorted(state["breakpoints"], key=lambda x: int(x)):
            print("  ->", point)


def registers_command(state):
    if not state["registers"]:
        print("No registers initialized.")
        return
    for name, value in state["registers"].items():
        print(f"{name}: {value}")


def interpret_command(command, state):
    parts = command.split()
    if not parts:
        return
    cmd = parts[0]

    if cmd == "quit":
        exit(0)

    elif cmd == "help":
        print_help()

    elif cmd == "page-step":
        page_step_command(state)

    elif cmd == "single-step":
        single_step_command(state)

    elif cmd == "break" and len(parts) == 2:
        break_command(parts[1], state)

    elif cmd == "unbreak" and len(parts) == 2:
        unbreak_command(parts[1], state)

    elif cmd == "breakpoints":
        show_breakpoints(state)

    elif cmd == "registers":
        registers_command(state)

    else:
        print("no valid command")




def main():
    print("-- PYTHON CLI RSA STEPPER --")
    print("Type 'help' for commands.\n")

    state = {
        "breakpoints": set(),
        "registers": {},
        "rsa_trace": [],
        "trace_index": -1,
    }

  
    init_toy_rsa_trace(state)

    while True:
        command = input("cli> ")
        interpret_command(command, state)


if __name__ == "__main__":
    main()

#test for git 