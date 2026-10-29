#include <algorithm>
#include <cassert>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstring>
#define BLI_assert assert
#include "BLI_rand.hh"
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *out = std::fopen(argv[1], "wb");
  if (!out) return 3;
  const uint32_t seeds[] = {0,1,2,42,65535,65536,1234567,2147483647,2147483648,4294967295};
  for (uint32_t seed : seeds) {
    blender::RandomNumberGenerator rng(seed);
    for (int i=0; i<4096; ++i) {
      const float value = rng.get_float();
      uint32_t bits;
      std::memcpy(&bits, &value, sizeof(bits));
      for (int b=0; b<4; ++b) if (std::fputc((bits >> (b*8)) & 255, out) == EOF) return 4;
    }
  }
  if (std::fclose(out)) return 5;
  blender::RandomNumberGenerator rng(42);
  for (int i=0; i<1048576; ++i) {
    const float value = rng.get_float();
    uint32_t bits;
    std::memcpy(&bits, &value, sizeof(bits));
    for (int b=0; b<4; ++b) if (std::putchar((bits >> (b*8)) & 255) == EOF) return 6;
  }
  return std::ferror(stdout) ? 7 : 0;
}
