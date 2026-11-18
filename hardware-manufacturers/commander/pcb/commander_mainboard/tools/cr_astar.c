/* Search core of tools/cpu_ram_board.py (the commander_cpu_ram board): A* on a multi-layer routing grid with
 * through vias, with PathFinder costs (present congestion x history), and a stamping routine for the clearance
 * zones.  Compiled on demand by cpu_ram_board.py (gcc -O2 -shared) into a DLL in the temp directory.
 *
 * Grid: W x H cells per layer, L routing layers, arrays flattened as [l * W * H + j * W + i].
 *   tho   int16   per layer: hard owner of the cell for a TRACK centre (-1 free, -2 several nets, else net id)
 *   vho   int16   one plane: hard owner for a VIA centre (through via: all layers already combined)
 *   occt  uint16  per layer: how many routed jobs' track keep-out zones cover the cell (soft)
 *   occv  uint16  one plane: the same for via keep-out zones
 *   hist  float   per layer, histv one plane: PathFinder history costs
 */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

typedef struct { float f; int64_t s; } HN;
static HN *heap = 0;
static int64_t hn = 0, hcap = 0;

static void hpush(float f, int64_t s) {
    if (hn == hcap) {
        hcap = hcap ? hcap * 2 : (1 << 16);
        heap = (HN *)realloc(heap, (size_t)hcap * sizeof(HN));
    }
    int64_t i = hn++;
    while (i > 0) {
        int64_t p = (i - 1) / 2;
        if (heap[p].f <= f) break;
        heap[i] = heap[p];
        i = p;
    }
    heap[i].f = f;
    heap[i].s = s;
}

static HN hpop(void) {
    HN top = heap[0], last = heap[--hn];
    int64_t i = 0;
    for (;;) {
        int64_t l = 2 * i + 1;
        if (l >= hn) break;
        int64_t r = l + 1, m = (r < hn && heap[r].f < heap[l].f) ? r : l;
        if (heap[m].f >= last.f) break;
        heap[i] = heap[m];
        i = m;
    }
    heap[i] = last;
    return top;
}

/* Add delta to arr over the union of discs (centre pi/pj, squared radius r2 in cells^2, strict <).  A cell is
 * counted once per call however many discs cover it (mark/epoch).  Used with +1 to add a job's zone, -1 to remove. */
EXPORT void stamp(uint16_t *arr, int W, int H, const int32_t *pi, const int32_t *pj, const float *r2, int n,
                  int delta, int32_t *mark, int32_t epoch) {
    for (int k = 0; k < n; k++) {
        float rr = r2[k];
        int R = (int)ceilf(sqrtf(rr));
        int ci = pi[k], cj = pj[k];
        for (int dj = -R; dj <= R; dj++) {
            int j = cj + dj;
            if (j < 0 || j >= H) continue;
            for (int di = -R; di <= R; di++) {
                if ((float)(di * di + dj * dj) >= rr) continue;
                int i = ci + di;
                if (i < 0 || i >= W) continue;
                int64_t c = (int64_t)j * W + i;
                if (mark[c] == epoch) continue;
                mark[c] = epoch;
                arr[c] = (uint16_t)(arr[c] + delta);
            }
        }
    }
}

static inline int blocked(int16_t o, int net) { return o != -1 && o != net; }

/* One connection.  starts: global states (l * N + c); goal: uint8 mask over global states, or goalvia = 1: the
 * search ends by dropping a via anywhere a via of this net may stand (a pad's way to a plane).  Search confined to
 * the box [i0, i1) x [j0, j1).  pres < 0: cells covered by another job's zone are forbidden (final clean-up).
 * Returns the number of states written to out (start ... end), 0 when there is no way, -1 when the budget ran out. */
EXPORT int astar(int W, int H, int L, const int16_t *tho, const int16_t *vho, const uint16_t *occt,
                 const uint16_t *occv, const float *hist, const float *histv, const float *lcost,
                 const uint8_t *lallow, int net, float pres, float viacost, int i0, int j0, int i1, int j1,
                 const int64_t *starts, int nstart, const uint8_t *goal, int goalvia, int gi0, int gj0, int gi1,
                 int gj1, float hw, int64_t maxexp, int64_t *out, int outcap) {
    const int64_t N = (int64_t)W * H;
    const int bw = i1 - i0, bh = j1 - j0;
    const int64_t BN = (int64_t)bw * bh, S = BN * L;
    float *g = (float *)malloc((size_t)S * sizeof(float));
    int64_t *par = (int64_t *)malloc((size_t)S * sizeof(int64_t));
    uint8_t *closed = (uint8_t *)calloc((size_t)S, 1);
    if (!g || !par || !closed) {
        free(g); free(par); free(closed);
        return -2;
    }
    for (int64_t k = 0; k < S; k++) g[k] = 1e30f;
    float lmin = 1e30f;
    for (int l = 0; l < L; l++)
        if (lallow[l] && lcost[l] < lmin) lmin = lcost[l];
    hn = 0;
    static const int di8[8] = {1, -1, 0, 0, 1, 1, -1, -1};
    static const int dj8[8] = {0, 0, 1, -1, 1, -1, 1, -1};
    const int hard = pres < 0;
#define HEUR(ii, jj)                                                                                            \
    (goalvia ? 0.0f : ({                                                                                        \
        int dx_ = (ii) < gi0 ? gi0 - (ii) : ((ii) > gi1 ? (ii) - gi1 : 0);                                     \
        int dy_ = (jj) < gj0 ? gj0 - (jj) : ((jj) > gj1 ? (jj) - gj1 : 0);                                     \
        int mx_ = dx_ > dy_ ? dx_ : dy_, mn_ = dx_ > dy_ ? dy_ : dx_;                                           \
        hw * lmin * ((float)mx_ + 0.41421356f * (float)mn_);                                                    \
    }))
    for (int k = 0; k < nstart; k++) {
        int64_t s = starts[k];
        int l = (int)(s / N);
        int64_t c = s % N;
        int i = (int)(c % W), j = (int)(c / W);
        if (i < i0 || i >= i1 || j < j0 || j >= j1 || !lallow[l]) continue;
        int64_t ls = (int64_t)l * BN + (int64_t)(j - j0) * bw + (i - i0);
        if (g[ls] <= 0) continue;
        g[ls] = 0;
        par[ls] = -1;
        hpush(HEUR(i, j), ls);
    }
    int64_t found = -1, exp = 0, bestls = -1;
    float bestg = 1e30f;
    int budget = 0;
    while (hn) {
        HN t = hpop();
        if (t.s == S) {                     /* the "via dropped" pseudo state of a goalvia search */
            if (t.f <= bestg + 1e-4f) { found = bestls; break; }
            continue;
        }
        int64_t ls = t.s;
        if (closed[ls]) continue;
        closed[ls] = 1;
        if (++exp > maxexp) { budget = 1; break; }
        int l = (int)(ls / BN);
        int64_t r = ls % BN;
        int i = (int)(r % bw) + i0, j = (int)(r / bw) + j0;
        int64_t gc = (int64_t)j * W + i;
        if (goal[(int64_t)l * N + gc]) { found = ls; break; }     /* (a goalvia search may also end on its net's copper) */
        float gcur = g[ls];
        for (int d = 0; d < 8; d++) {
            int ni = i + di8[d], nj = j + dj8[d];
            if (ni < i0 || ni >= i1 || nj < j0 || nj >= j1) continue;
            int64_t nc = (int64_t)nj * W + ni, gs = (int64_t)l * N + nc;
            if (blocked(tho[gs], net)) continue;
            if (d >= 4) {                   /* no corner cutting past a hard obstacle */
                if (blocked(tho[(int64_t)l * N + (int64_t)j * W + ni], net)) continue;
                if (blocked(tho[(int64_t)l * N + (int64_t)nj * W + i], net)) continue;
            }
            if (hard && occt[gs]) continue;
            int64_t nls = (int64_t)l * BN + (int64_t)(nj - j0) * bw + (ni - i0);
            if (closed[nls]) continue;
            float c = (d < 4 ? 1.0f : 1.41421356f) * lcost[l] * (1.0f + hist[gs]) * (1.0f + (hard ? 0.0f : pres * occt[gs]));
            float ng = gcur + c;
            if (ng < g[nls]) {
                g[nls] = ng;
                par[nls] = ls;
                hpush(ng + HEUR(ni, nj), nls);
            }
        }
        if (!blocked(vho[gc], net) && !(hard && occv[gc])) {
            float vc = viacost * (1.0f + histv[gc]) * (1.0f + (hard ? 0.0f : pres * occv[gc]));
            if (goalvia) {
                if (gcur + vc < bestg) {
                    bestg = gcur + vc;
                    bestls = ls;
                    hpush(bestg, S);
                }
            } else {
                for (int l2 = 0; l2 < L; l2++) {
                    if (l2 == l || !lallow[l2]) continue;
                    int64_t nls = (int64_t)l2 * BN + r;
                    if (closed[nls]) continue;
                    int64_t gs2 = (int64_t)l2 * N + gc;
                    if (blocked(tho[gs2], net)) continue;
                    float ng = gcur + vc;
                    if (ng < g[nls]) {
                        g[nls] = ng;
                        par[nls] = ls;
                        hpush(ng + HEUR(i, j), nls);
                    }
                }
            }
        }
    }
    int n = 0;
    if (found >= 0) {
        int64_t k = found;
        while (k >= 0 && n < outcap) {
            int l = (int)(k / BN);
            int64_t r = k % BN;
            int i = (int)(r % bw) + i0, j = (int)(r / bw) + j0;
            out[n++] = (int64_t)l * N + (int64_t)j * W + i;
            k = par[k];
        }
        for (int a = 0, b = n - 1; a < b; a++, b--) {   /* start first */
            int64_t tmp = out[a]; out[a] = out[b]; out[b] = tmp;
        }
    }
    free(g); free(par); free(closed);
    if (found < 0) return budget ? -1 : 0;
    return n;
}
