#!/usr/bin/env python3
"""Partial UWP source adaptation for WiiCompiled v0.2.31 (GPL-3.0).

Apply only to a disposable runtime overlay. Exact anchors are checked before
any writes. This is not yet the full Xbox runtime port.
"""
import argparse
from pathlib import Path

MARKER = "// RR_ENHANCED_UWP_V0231"

def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError("missing or ambiguous anchor: " + old[:100])
    return s.replace(old, new, 1)

def data_config(s):
    old = "inline std::filesystem::path ApplicationDataDirectory() {\n"
    s = once(s, old, old + "#if defined(MKW_UWP)\n    return RuntimePlatform::ApplicationDataDirectory(kApplicationDirectoryName);\n#else\n")
    return once(s, "    return std::filesystem::current_path() / kApplicationDirectoryName;\n}", "    return std::filesystem::current_path() / kApplicationDirectoryName;\n#endif\n}")

def data_platform(s):
    s = once(s, "#include <cstdlib>", "#include <cstdlib>\n#if defined(MKW_UWP)\n#include <SDL3/SDL.h>\n#include <stdexcept>\n#endif")
    old = "std::filesystem::path ApplicationDataDirectory(std::string_view applicationName) {\n#if defined(_WIN32)"
    return once(s, old, """std::filesystem::path ApplicationDataDirectory(std::string_view applicationName) {
#if defined(MKW_UWP)
    const std::string name(applicationName);
    char* raw = SDL_GetPrefPath("", name.c_str());
    if (!raw) throw std::runtime_error("SDL_GetPrefPath failed");
    struct FreePath { void operator()(char* p) const { SDL_free(p); } };
    std::unique_ptr<char, FreePath> guard(raw);
    return std::filesystem::u8path(raw);
#elif defined(_WIN32)""").replace("#include <stdexcept>", "#include <stdexcept>\n#include <memory>\n#include <string>", 1)

def fibers(s):
    s = once(s, "    void* context = ConvertThreadToFiber(nullptr);", """#if defined(MKW_UWP)
    void* context = ConvertThreadToFiberEx(nullptr, 0);
#else
    void* context = ConvertThreadToFiber(nullptr);
#endif""")
    return once(s, "    return CreateFiber(stackSize, entry, argument);", """#if defined(MKW_UWP)
    return CreateFiberEx(stackSize, 0, 0, entry, argument);
#else
    return CreateFiber(stackSize, entry, argument);
#endif""")

def discord(s):
    old = '#include "discord_presence.h"\n'
    return once(s, old, old + """#if defined(MKW_UWP)
namespace DiscordPresence {
void Initialize(const std::string&, const std::string&) {}
void SetClient(const std::string&) {}
void SetActivity(Activity) {}
void Reset() {}
void Shutdown() {}
}
#else
""") + "\n#endif // MKW_UWP\n"

def crypto(s):
    old = "#if CRYPTOPP_MSC_VERSION >= 1600\n\t\t\t\t(stdext::make_unchecked_array_iterator(scan)"
    return once(s, old, "#if CRYPTOPP_MSC_VERSION >= 1600 && !defined(MKW_UWP)\n\t\t\t\t(stdext::make_unchecked_array_iterator(scan)")

def ssl(s):
    # Keep common socket helpers but use the existing unsupported-platform TLS
    # implementation; reject every SSL request rather than allowing plaintext.
    if s.count("#ifdef _WIN32") != 3:
        raise ValueError("SSL platform guard count changed")
    s = s.replace("#ifdef _WIN32", "#if defined(_WIN32) && !defined(MKW_UWP)")
    old = "int32_t HandleSslIoctlv(uint32_t cmd, const std::vector<IoVector>& in, const std::vector<IoVector>& out) {"
    return once(s, old, old + """
#if defined(MKW_UWP)
    (void)cmd;
    (void)out;
    WriteSslReturn(in, SSL_ERR_FAILED);
    return 0;
#endif""")

def ssl_header(s):
    return once(s, "#define SECURITY_WIN32\n#include <security.h>\n#include <schannel.h>", "#if !defined(MKW_UWP)\n#define SECURITY_WIN32\n#include <security.h>\n#include <schannel.h>\n#endif")

PATCHES = {
    "include/runtime_config.h": data_config,
    "src/platform/host_platform.cpp": data_platform,
    "src/host_context.cpp": fibers,
    "src/discord_presence.cpp": discord,
    "third_party/cryptopp/zdeflate.cpp": crypto,
    "src/hle/net/network_ssl.cpp": ssl,
    "src/hle/net/network_internal.h": ssl_header,
}

def apply(root, check=False):
    staged = {}
    for rel, transform in PATCHES.items():
        p = root / rel
        s = p.read_text(encoding="utf-8")
        if s.startswith(MARKER+"\n"):
            continue
        try:
            updated = transform(s)
        except ValueError as e:
            raise ValueError(f"{rel}: {e}") from e
        staged[p] = MARKER+"\n"+updated
    if not check:
        for p, s in staged.items():
            p.write_text(s, encoding="utf-8", newline="\n")
    return len(staged)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("runtime", type=Path)
    p.add_argument("--check", action="store_true")
    a=p.parse_args()
    try:
        n=apply(a.runtime, a.check)
    except (OSError,ValueError) as e:
        p.exit(1,str(e)+"\n")
    print(f"{n} files {'would be changed' if a.check else 'changed'}; partial adaptation only")

if __name__=="__main__":
    main()
