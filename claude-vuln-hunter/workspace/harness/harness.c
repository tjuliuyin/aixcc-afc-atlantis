/*
 * libFuzzer harness. Compiled with -fsanitize=address,fuzzer.
 * When run as `./harness <file>` it replays a single input (PoV reproduce mode),
 * which is exactly how tools/reproduce.py drives it.
 */
#include <stdint.h>
#include <stddef.h>
#include "../target/parser.h"

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    parse_record(data, size);
    return 0;
}
