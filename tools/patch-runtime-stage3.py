#!/usr/bin/env python3
"""Address the first actual MSVC ABI UWP compiler diagnostics."""
import argparse
from pathlib import Path

MARK="// RR_ENHANCED_UWP_STAGE3"
def veh(s):
    old="#include <windows.h>\n"
    if s.count(old)!=1: raise ValueError("windows.h anchor changed")
    return s.replace(old,old+"""#if defined(MKW_UWP)
// These exports are present in the Xbox port's kernel32 ABI but hidden by
// the Windows Store SDK headers. Keep the original fault handling active.
extern "C" WINBASEAPI PVOID WINAPI AddVectoredExceptionHandler(ULONG, PVECTORED_EXCEPTION_HANDLER);
extern "C" WINBASEAPI ULONG WINAPI RemoveVectoredExceptionHandler(PVOID);
#endif
""",1)
def crypto(s):
    old="#if defined(_STDEXT_BEGIN) && !(defined(CRYPTOPP_MSC_VERSION)"
    if s.count(old)!=1: raise ValueError("stdext guard anchor changed")
    return s.replace(old,"#if !defined(MKW_UWP) && defined(_STDEXT_BEGIN) && !(defined(CRYPTOPP_MSC_VERSION)",1)
def main():
    p=argparse.ArgumentParser();p.add_argument("root",type=Path);p.add_argument("--check",action="store_true");a=p.parse_args()
    staged={}
    for rel,fn in {"src/main.cpp":veh,"src/guest_flat_memory.cpp":veh,"third_party/cryptopp/zdeflate.cpp":crypto}.items():
        path=a.root/rel
        s=path.read_text(encoding="utf-8")
        if s.startswith(MARK+"\n"): continue
        staged[path]=MARK+"\n"+fn(s)
    if not a.check:
        for p,s in staged.items(): p.write_text(s,encoding="utf-8",newline="\n")
    print(f"{len(staged)} files {'would be changed' if a.check else 'changed'}")
if __name__=="__main__": main()
