//! Ear clipping in a normalized dominant-axis projection. Source corner indices survive.
use crate::scene::{Result, SceneError};
const EPS: f64 = 1e-12;
type Point = [f64; 2];

fn cross(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}
fn orient(a: Point, b: Point, c: Point) -> f64 {
    (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
}
fn on_segment(a: Point, b: Point, p: Point) -> bool {
    orient(a, b, p).abs() <= EPS
        && (0..2).all(|i| p[i] >= a[i].min(b[i]) - EPS && p[i] <= a[i].max(b[i]) + EPS)
}
fn intersects(a: Point, b: Point, c: Point, d: Point) -> bool {
    if (0..2)
        .any(|i| a[i].max(b[i]) + EPS < c[i].min(d[i]) || c[i].max(d[i]) + EPS < a[i].min(b[i]))
    {
        return false;
    }
    let ab = [orient(a, b, c), orient(a, b, d)];
    let cd = [orient(c, d, a), orient(c, d, b)];
    (ab[0] * ab[1] < 0. && cd[0] * cd[1] < 0.)
        || on_segment(a, b, c)
        || on_segment(a, b, d)
        || on_segment(c, d, a)
        || on_segment(c, d, b)
}
fn same(a: Point, b: Point) -> bool {
    (0..2).all(|i| (a[i] - b[i]).abs() <= EPS)
}
fn error(message: &str) -> SceneError {
    SceneError(message.into())
}

pub(super) fn triangulate(points: &[[f64; 3]]) -> Result<Vec<[usize; 3]>> {
    let mut local = Vec::with_capacity(points.len());
    let mut scale = 0_f64;
    for point in points {
        let p: [f64; 3] = std::array::from_fn(|i| point[i] - points[0][i]);
        if !p.iter().all(|n| n.is_finite()) {
            return Err(error("polygon exceeds tessellation range"));
        }
        for n in p {
            scale = scale.max(n.abs());
        }
        local.push(p);
    }
    if scale == 0. {
        return Ok(Vec::new());
    }
    for p in &mut local {
        for n in p {
            *n /= scale;
        }
    }
    let mut normal = [0_f64; 3];
    for i in 0..local.len() {
        let c = cross(local[i], local[(i + 1) % local.len()]);
        for j in 0..3 {
            normal[j] += c[j];
        }
    }
    // A crossing loop can cancel its Newell normal. Inspect a noncollinear
    // projection instead of silently calling the loop degenerate.
    if normal.iter().all(|n| n.abs() <= EPS) {
        let extent = |p: &[f64; 3]| p.iter().map(|n| n.abs()).fold(0_f64, f64::max);
        let direction = local
            .iter()
            .max_by(|a, b| extent(a).total_cmp(&extent(b)))
            .expect("polygon points");
        normal = local
            .iter()
            .map(|p| cross(*direction, *p))
            .find(|c| c.iter().any(|n| n.abs() > EPS))
            .unwrap_or([0.; 3]);
        if normal.iter().all(|n| n.abs() <= EPS) {
            return Ok(Vec::new());
        }
    }
    let axis = (0..3)
        .max_by(|a, b| normal[*a].abs().total_cmp(&normal[*b].abs()))
        .expect("three axes");
    let projected: Vec<Point> = local
        .iter()
        .map(|p| match axis {
            0 => [p[1], p[2]],
            1 => [p[2], p[0]],
            _ => [p[0], p[1]],
        })
        .collect();
    let mut ring = Vec::new();
    for i in 0..projected.len() {
        if ring
            .last()
            .is_none_or(|last| !same(projected[*last], projected[i]))
        {
            ring.push(i);
        }
    }
    while ring.len() > 1 && same(projected[ring[0]], projected[*ring.last().unwrap()]) {
        ring.pop();
    }
    loop {
        if ring.len() < 3 {
            return Ok(Vec::new());
        }
        let redundant = (0..ring.len()).find(|i| {
            let a = projected[ring[(*i + ring.len() - 1) % ring.len()]];
            let b = projected[ring[*i]];
            let c = projected[ring[(*i + 1) % ring.len()]];
            on_segment(a, c, b)
        });
        match redundant {
            Some(i) => {
                ring.remove(i);
            }
            None => break,
        }
    }
    for i in 0..ring.len() {
        for j in i + 1..ring.len() {
            if j == i + 1 || (i == 0 && j == ring.len() - 1) {
                continue;
            }
            if intersects(
                projected[ring[i]],
                projected[ring[(i + 1) % ring.len()]],
                projected[ring[j]],
                projected[ring[(j + 1) % ring.len()]],
            ) {
                return Err(error("self-intersecting polygon projection"));
            }
        }
    }
    let area: f64 = (0..ring.len())
        .map(|i| {
            let a = projected[ring[i]];
            let b = projected[ring[(i + 1) % ring.len()]];
            a[0] * b[1] - a[1] * b[0]
        })
        .sum();
    if area.abs() <= EPS {
        return Ok(Vec::new());
    }
    let sign = area.signum();
    let mut triangles = Vec::with_capacity(ring.len() - 2);
    if (0..ring.len()).all(|i| {
        sign * orient(
            projected[ring[(i + ring.len() - 1) % ring.len()]],
            projected[ring[i]],
            projected[ring[(i + 1) % ring.len()]],
        ) > EPS
    }) {
        for i in 1..ring.len() - 1 {
            triangles.push([ring[0], ring[i], ring[i + 1]]);
        }
        return Ok(triangles);
    }
    while ring.len() > 3 {
        let ear = (0..ring.len())
            .find(|i| {
                let indices = [
                    ring[(*i + ring.len() - 1) % ring.len()],
                    ring[*i],
                    ring[(*i + 1) % ring.len()],
                ];
                let [a, b, c] = indices.map(|i| projected[i]);
                sign * orient(a, b, c) > EPS
                    && !ring.iter().any(|p| {
                        !indices.contains(p)
                            && [
                                orient(a, b, projected[*p]),
                                orient(b, c, projected[*p]),
                                orient(c, a, projected[*p]),
                            ]
                            .into_iter()
                            .all(|o| sign * o >= -EPS)
                    })
            })
            .ok_or_else(|| error("cannot tessellate polygon projection"))?;
        triangles.push([
            ring[(ear + ring.len() - 1) % ring.len()],
            ring[ear],
            ring[(ear + 1) % ring.len()],
        ]);
        ring.remove(ear);
    }
    triangles.push([ring[0], ring[1], ring[2]]);
    Ok(triangles)
}
