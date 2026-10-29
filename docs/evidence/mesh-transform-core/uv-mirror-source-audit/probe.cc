#include <cstdint>
#include <cstdlib>
#include <cstdio>
using MirrTopoHash_t = unsigned int;
static int mirrtopo_hash_sort(const void *l1, const void *l2)
{
  if (MirrTopoHash_t(intptr_t(l1)) > MirrTopoHash_t(intptr_t(l2))) {
    return 1;
  }
  if (MirrTopoHash_t(intptr_t(l1)) < MirrTopoHash_t(intptr_t(l2))) {
    return -1;
  }
  return 0;
}

int main(){ MirrTopoHash_t v[]={9,1,9,2,2,1}; qsort(v,6,sizeof(*v),mirrtopo_hash_sort); for(auto x:v) printf("%u ",x); puts(""); }
