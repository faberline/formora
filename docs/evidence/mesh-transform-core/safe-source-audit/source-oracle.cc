// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#define MATH_STANDALONE
#define BLI_assert(x) assert(x)
#define UNLIKELY(x) (x)
#define SWAP(t,a,b) std::swap(a,b)
static int min_ii(int a,int b){return std::min(a,b);}
static int max_ii(int a,int b){return std::max(a,b);}
static float max_ff(float a,float b){return std::max(a,b);}
static void copy_m4_m4(float a[4][4],const float b[4][4]){std::memcpy(a,b,sizeof(float)*16);}
static void zero_m4(float a[4][4]){std::memset(a,0,sizeof(float)*16);}
static void zero_v4(float a[4]){std::memset(a,0,sizeof(float)*4);}
void svd_m4(float U[4][4], float s[4], float V[4][4], float A_[4][4])
{
  /* NOTE: originally from TNT (template numeric toolkit) matrix library.
   * https://math.nist.gov/tnt */

  float A[4][4];
  float work1[4], work2[4];
  int m = 4;
  int n = 4;
  int maxiter = 200;
  int nu = min_ii(m, n);

  float *work = work1;
  float *e = work2;
  float eps;

  int i = 0, j = 0, k = 0, p, pp, iter;

  /* Reduce A to bidiagonal form, storing the diagonal elements
   * in s and the super-diagonal elements in e. */

  int nct = min_ii(m - 1, n);
  int nrt = max_ii(0, min_ii(n - 2, m));

  copy_m4_m4(A, A_);
  zero_m4(U);
  zero_v4(s);

  for (k = 0; k < max_ii(nct, nrt); k++) {
    if (k < nct) {

      /* Compute the transformation for the k-th column and
       * place the k-th diagonal in s[k].
       * Compute 2-norm of k-th column without under/overflow. */
      s[k] = 0;
      for (i = k; i < m; i++) {
        s[k] = hypotf(s[k], A[i][k]);
      }
      if (s[k] != 0.0f) {
        float invsk;
        if (A[k][k] < 0.0f) {
          s[k] = -s[k];
        }
        invsk = 1.0f / s[k];
        for (i = k; i < m; i++) {
          A[i][k] *= invsk;
        }
        A[k][k] += 1.0f;
      }
      s[k] = -s[k];
    }
    for (j = k + 1; j < n; j++) {
      if ((k < nct) && (s[k] != 0.0f)) {

        /* Apply the transformation. */

        float t = 0;
        for (i = k; i < m; i++) {
          t += A[i][k] * A[i][j];
        }
        t = -t / A[k][k];
        for (i = k; i < m; i++) {
          A[i][j] += t * A[i][k];
        }
      }

      /* Place the k-th row of A into e for the */
      /* subsequent calculation of the row transformation. */

      e[j] = A[k][j];
    }
    if (k < nct) {

      /* Place the transformation in U for subsequent back
       * multiplication. */

      for (i = k; i < m; i++) {
        U[i][k] = A[i][k];
      }
    }
    if (k < nrt) {

      /* Compute the k-th row transformation and place the
       * k-th super-diagonal in e[k].
       * Compute 2-norm without under/overflow. */
      e[k] = 0;
      for (i = k + 1; i < n; i++) {
        e[k] = hypotf(e[k], e[i]);
      }
      if (e[k] != 0.0f) {
        float invek;
        if (e[k + 1] < 0.0f) {
          e[k] = -e[k];
        }
        invek = 1.0f / e[k];
        for (i = k + 1; i < n; i++) {
          e[i] *= invek;
        }
        e[k + 1] += 1.0f;
      }
      e[k] = -e[k];
      if ((k + 1 < m) && (e[k] != 0.0f)) {
        float invek1;

        /* Apply the transformation. */

        for (i = k + 1; i < m; i++) {
          work[i] = 0.0f;
        }
        for (j = k + 1; j < n; j++) {
          for (i = k + 1; i < m; i++) {
            work[i] += e[j] * A[i][j];
          }
        }
        invek1 = 1.0f / e[k + 1];
        for (j = k + 1; j < n; j++) {
          float t = -e[j] * invek1;
          for (i = k + 1; i < m; i++) {
            A[i][j] += t * work[i];
          }
        }
      }

      /* Place the transformation in V for subsequent
       * back multiplication. */

      for (i = k + 1; i < n; i++) {
        V[i][k] = e[i];
      }
    }
  }

  /* Set up the final bidiagonal matrix or order p. */

  p = min_ii(n, m + 1);
  if (nct < n) {
    s[nct] = A[nct][nct];
  }
  if (m < p) {
    s[p - 1] = 0.0f;
  }
  if (nrt + 1 < p) {
    e[nrt] = A[nrt][p - 1];
  }
  e[p - 1] = 0.0f;

  /* If required, generate U. */

  for (j = nct; j < nu; j++) {
    for (i = 0; i < m; i++) {
      U[i][j] = 0.0f;
    }
    U[j][j] = 1.0f;
  }
  for (k = nct - 1; k >= 0; k--) {
    if (s[k] != 0.0f) {
      for (j = k + 1; j < nu; j++) {
        float t = 0;
        for (i = k; i < m; i++) {
          t += U[i][k] * U[i][j];
        }
        t = -t / U[k][k];
        for (i = k; i < m; i++) {
          U[i][j] += t * U[i][k];
        }
      }
      for (i = k; i < m; i++) {
        U[i][k] = -U[i][k];
      }
      U[k][k] = 1.0f + U[k][k];
      for (i = 0; i < k - 1; i++) {
        U[i][k] = 0.0f;
      }
    }
    else {
      for (i = 0; i < m; i++) {
        U[i][k] = 0.0f;
      }
      U[k][k] = 1.0f;
    }
  }

  /* If required, generate V. */

  for (k = n - 1; k >= 0; k--) {
    if ((k < nrt) && (e[k] != 0.0f)) {
      for (j = k + 1; j < nu; j++) {
        float t = 0;
        for (i = k + 1; i < n; i++) {
          t += V[i][k] * V[i][j];
        }
        t = -t / V[k + 1][k];
        for (i = k + 1; i < n; i++) {
          V[i][j] += t * V[i][k];
        }
      }
    }
    for (i = 0; i < n; i++) {
      V[i][k] = 0.0f;
    }
    V[k][k] = 1.0f;
  }

  /* Main iteration loop for the singular values. */

  pp = p - 1;
  iter = 0;
  eps = powf(2.0f, -52.0f);
  while (p > 0) {
    int kase = 0;

    /* Test for maximum iterations to avoid infinite loop */
    if (maxiter == 0) {
      break;
    }
    maxiter--;

    /* This section of the program inspects for
     * negligible elements in the s and e arrays.  On
     * completion the variables kase and k are set as follows.
     *
     * kase = 1: if s(p) and e[k - 1] are negligible and k<p
     * kase = 2: if s(k) is negligible and k<p
     * kase = 3: if e[k - 1] is negligible, k<p, and
     *              s(k), ..., s(p) are not negligible (qr step).
     * kase = 4: if e(p - 1) is negligible (convergence). */

    for (k = p - 2; k >= -1; k--) {
      if (k == -1) {
        break;
      }
      if (fabsf(e[k]) <= eps * (fabsf(s[k]) + fabsf(s[k + 1]))) {
        e[k] = 0.0f;
        break;
      }
    }
    if (k == p - 2) {
      kase = 4;
    }
    else {
      int ks;
      for (ks = p - 1; ks >= k; ks--) {
        float t;
        if (ks == k) {
          break;
        }
        t = (ks != p ? fabsf(e[ks]) : 0.0f) + (ks != k + 1 ? fabsf(e[ks - 1]) : 0.0f);
        if (fabsf(s[ks]) <= eps * t) {
          s[ks] = 0.0f;
          break;
        }
      }
      if (ks == k) {
        kase = 3;
      }
      else if (ks == p - 1) {
        kase = 1;
      }
      else {
        kase = 2;
        k = ks;
      }
    }
    k++;

    /* Perform the task indicated by kase. */

    switch (kase) {

        /* Deflate negligible s(p). */

      case 1: {
        float f = e[p - 2];
        e[p - 2] = 0.0f;
        for (j = p - 2; j >= k; j--) {
          float t = hypotf(s[j], f);
          float invt = 1.0f / t;
          float cs = s[j] * invt;
          float sn = f * invt;
          s[j] = t;
          if (j != k) {
            f = -sn * e[j - 1];
            e[j - 1] = cs * e[j - 1];
          }

          for (i = 0; i < n; i++) {
            t = cs * V[i][j] + sn * V[i][p - 1];
            V[i][p - 1] = -sn * V[i][j] + cs * V[i][p - 1];
            V[i][j] = t;
          }
        }
        break;
      }

        /* Split at negligible s(k). */

      case 2: {
        float f = e[k - 1];
        e[k - 1] = 0.0f;
        for (j = k; j < p; j++) {
          float t = hypotf(s[j], f);
          float invt = 1.0f / t;
          float cs = s[j] * invt;
          float sn = f * invt;
          s[j] = t;
          f = -sn * e[j];
          e[j] = cs * e[j];

          for (i = 0; i < m; i++) {
            t = cs * U[i][j] + sn * U[i][k - 1];
            U[i][k - 1] = -sn * U[i][j] + cs * U[i][k - 1];
            U[i][j] = t;
          }
        }
        break;
      }

        /* Perform one qr step. */

      case 3: {

        /* Calculate the shift. */

        float scale = max_ff(
            max_ff(max_ff(max_ff(fabsf(s[p - 1]), fabsf(s[p - 2])), fabsf(e[p - 2])), fabsf(s[k])),
            fabsf(e[k]));
        float invscale = 1.0f / scale;
        float sp = s[p - 1] * invscale;
        float spm1 = s[p - 2] * invscale;
        float epm1 = e[p - 2] * invscale;
        float sk = s[k] * invscale;
        float ek = e[k] * invscale;
        float b = ((spm1 + sp) * (spm1 - sp) + epm1 * epm1) * 0.5f;
        float c = (sp * epm1) * (sp * epm1);
        float shift = 0.0f;
        float f, g;
        if ((b != 0.0f) || (c != 0.0f)) {
          shift = sqrtf(b * b + c);
          if (b < 0.0f) {
            shift = -shift;
          }
          shift = c / (b + shift);
        }
        f = (sk + sp) * (sk - sp) + shift;
        g = sk * ek;

        /* Chase zeros. */

        for (j = k; j < p - 1; j++) {
          float t = hypotf(f, g);
          /* NOTE(@brecht): division by zero checks added to avoid NaN. */
          float cs = (t == 0.0f) ? 0.0f : f / t;
          float sn = (t == 0.0f) ? 0.0f : g / t;
          if (j != k) {
            e[j - 1] = t;
          }
          f = cs * s[j] + sn * e[j];
          e[j] = cs * e[j] - sn * s[j];
          g = sn * s[j + 1];
          s[j + 1] = cs * s[j + 1];

          for (i = 0; i < n; i++) {
            t = cs * V[i][j] + sn * V[i][j + 1];
            V[i][j + 1] = -sn * V[i][j] + cs * V[i][j + 1];
            V[i][j] = t;
          }

          t = hypotf(f, g);
          /* NOTE(@brecht): division by zero checks added to avoid NaN. */
          cs = (t == 0.0f) ? 0.0f : f / t;
          sn = (t == 0.0f) ? 0.0f : g / t;
          s[j] = t;
          f = cs * e[j] + sn * s[j + 1];
          s[j + 1] = -sn * e[j] + cs * s[j + 1];
          g = sn * e[j + 1];
          e[j + 1] = cs * e[j + 1];
          if (j < m - 1) {
            for (i = 0; i < m; i++) {
              t = cs * U[i][j] + sn * U[i][j + 1];
              U[i][j + 1] = -sn * U[i][j] + cs * U[i][j + 1];
              U[i][j] = t;
            }
          }
        }
        e[p - 2] = f;
        iter = iter + 1;
        break;
      }
        /* Convergence. */

      case 4: {

        /* Make the singular values positive. */

        if (s[k] <= 0.0f) {
          s[k] = (s[k] < 0.0f ? -s[k] : 0.0f);

          for (i = 0; i <= pp; i++) {
            V[i][k] = -V[i][k];
          }
        }

        /* Order the singular values. */

        while (k < pp) {
          float t;
          if (s[k] >= s[k + 1]) {
            break;
          }
          t = s[k];
          s[k] = s[k + 1];
          s[k + 1] = t;
          if (k < n - 1) {
            for (i = 0; i < n; i++) {
              t = V[i][k + 1];
              V[i][k + 1] = V[i][k];
              V[i][k] = t;
            }
          }
          if (k < m - 1) {
            for (i = 0; i < m; i++) {
              t = U[i][k + 1];
              U[i][k + 1] = U[i][k];
              U[i][k] = t;
            }
          }
          k++;
        }
        iter = 0;
        p--;
        break;
      }
    }
  }
}

bool invert_m4_m4_fallback(float inverse[4][4], const float mat[4][4])
{
#ifndef MATH_STANDALONE
  if (EIG_invert_m4_m4(inverse, mat)) {
    return true;
  }
#endif

  int i, j, k;
  double temp;
  float tempmat[4][4];
  float max;
  int maxj;

  BLI_assert(inverse != mat);

  /* Set inverse to identity */
  for (i = 0; i < 4; i++) {
    for (j = 0; j < 4; j++) {
      inverse[i][j] = 0;
    }
  }
  for (i = 0; i < 4; i++) {
    inverse[i][i] = 1;
  }

  /* Copy original matrix so we don't mess it up */
  for (i = 0; i < 4; i++) {
    for (j = 0; j < 4; j++) {
      tempmat[i][j] = mat[i][j];
    }
  }

  for (i = 0; i < 4; i++) {
    /* Look for row with max pivot */
    max = fabsf(tempmat[i][i]);
    maxj = i;
    for (j = i + 1; j < 4; j++) {
      if (fabsf(tempmat[j][i]) > max) {
        max = fabsf(tempmat[j][i]);
        maxj = j;
      }
    }
    /* Swap rows if necessary */
    if (maxj != i) {
      for (k = 0; k < 4; k++) {
        SWAP(float, tempmat[i][k], tempmat[maxj][k]);
        SWAP(float, inverse[i][k], inverse[maxj][k]);
      }
    }

    if (UNLIKELY(tempmat[i][i] == 0.0f)) {
      return false; /* No non-zero pivot */
    }
    temp = double(tempmat[i][i]);
    for (k = 0; k < 4; k++) {
      tempmat[i][k] = float(double(tempmat[i][k]) / temp);
      inverse[i][k] = float(double(inverse[i][k]) / temp);
    }
    for (j = 0; j < 4; j++) {
      if (j != i) {
        temp = tempmat[j][i];
        for (k = 0; k < 4; k++) {
          tempmat[j][k] -= float(double(tempmat[i][k]) * temp);
          inverse[j][k] -= float(double(inverse[i][k]) * temp);
        }
      }
    }
  }
  return true;
}

int main(){
float matrices[2][4][4]={{{1,2,3,0},{2,4,6,0},{-1,-2,-3,0},{0,0,0,1}},{{1,2,0,0},{0,1,1,0},{1,3,1,0},{0,0,0,1}}};
for(auto &a:matrices){float u[4][4],v[4][4],s[4];svd_m4(u,s,v,a);std::printf("singular_values: %.9g %.9g %.9g %.9g\n",s[0],s[1],s[2],s[3]);}
float raw[4][4]={{1,0,0,0},{0,0,0,0},{0,0,1,0},{2,3,4,1}},inverse[4][4];bool ok=invert_m4_m4_fallback(inverse,raw);
std::printf("pivot_inverse_success: %d; pivot: ",ok);float point[3]={2,3,4};for(int r=0;r<3;r++)std::printf("%.9g ",inverse[0][r]*point[0]+inverse[1][r]*point[1]+inverse[2][r]*point[2]+inverse[3][r]);std::printf("\n");
}
