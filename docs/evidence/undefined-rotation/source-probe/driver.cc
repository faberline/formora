#include <cassert>
#include <cstdio>
#define BLI_assert assert
enum { CON_APPLY=1<<0, CON_AXIS0=1<<1, CON_AXIS1=1<<2, CON_AXIS2=1<<3 };
struct TransInfo { struct { int mode; } con; };
static void copy_v3_v3(float *out,const float *in) { for(int i=0;i<3;++i) out[i]=in[i]; }
static void constraints_rotation_impl(const TransInfo *t,
                                      const float axismtx[3][3],
                                      float r_axis[3])
{
  BLI_assert(t->con.mode & CON_APPLY);
  int mode = t->con.mode & (CON_AXIS0 | CON_AXIS1 | CON_AXIS2);

  switch (mode) {
    case CON_AXIS0:
    case (CON_AXIS1 | CON_AXIS2):
      copy_v3_v3(r_axis, axismtx[0]);
      break;
    case CON_AXIS1:
    case (CON_AXIS0 | CON_AXIS2):
      copy_v3_v3(r_axis, axismtx[1]);
      break;
    case CON_AXIS2:
    case (CON_AXIS0 | CON_AXIS1):
      copy_v3_v3(r_axis, axismtx[2]);
      break;
  }
}
int main() {
  const float basis[3][3]={{2,3,5},{7,11,13},{17,19,23}};
  for(int mask=0;mask<8;++mask) {
    TransInfo t{{CON_APPLY | (mask<<1)}};
    float axis[3]={41,-43,47};
    constraints_rotation_impl(&t,basis,axis);
    std::printf("{\"mask\":%d,\"axis\":[%.9g,%.9g,%.9g]}\n",mask,axis[0],axis[1],axis[2]);
  }
}
