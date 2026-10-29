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
