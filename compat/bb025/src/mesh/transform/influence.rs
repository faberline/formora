// SPDX-FileCopyrightText: 2001-2002 NaN Holding BV. All rights reserved.
// SPDX-License-Identifier: GPL-2.0-or-later
use super::{
    Falloff, RandomAlgorithm, Request, Vector, context::Context, dot, finite, geodesic,
    random::Stream, sub,
};
use crate::scene::{Result, SceneError};

// A balanced point tree bounds sparse-selection nearest-distance work.
struct Tree {
    point: Vector,
    axis: usize,
    left: Option<Box<Tree>>,
    right: Option<Box<Tree>>,
}
impl Tree {
    fn build(points: &mut [Vector], depth: usize) -> Option<Box<Self>> {
        if points.is_empty() {
            return None;
        }
        let axis = depth % 3;
        let mid = points.len() / 2;
        points.select_nth_unstable_by(mid, |a, b| {
            a[axis]
                .total_cmp(&b[axis])
                .then_with(|| a[0].total_cmp(&b[0]))
                .then_with(|| a[1].total_cmp(&b[1]))
                .then_with(|| a[2].total_cmp(&b[2]))
        });
        let point = points[mid];
        let (left, right) = points.split_at_mut(mid);
        Some(Box::new(Self {
            point,
            axis,
            left: Self::build(left, depth + 1),
            right: Self::build(&mut right[1..], depth + 1),
        }))
    }
    fn nearest(&self, point: Vector, best: &mut f32) {
        let delta = sub(point, self.point);
        *best = best.min(dot(delta, delta));
        let split = delta[self.axis];
        let (first, second) = if split <= 0. {
            (&self.left, &self.right)
        } else {
            (&self.right, &self.left)
        };
        if let Some(child) = first {
            child.nearest(point, best);
        }
        if split * split <= *best {
            if let Some(child) = second {
                child.nearest(point, best);
            }
        }
    }
}
pub(super) struct Influence {
    pub weights: Vec<f32>,
    pub origins: Option<Vec<usize>>,
}
pub(super) fn calculate(context: &Context, request: &Request) -> Result<Influence> {
    let Some(p) = &request.proportional else {
        return Ok(Influence {
            weights: context
                .selected
                .iter()
                .map(|s| if *s { 1. } else { 0. })
                .collect(),
            origins: None,
        });
    };
    finite(&[p.radius])?;
    if p.radius <= 0. || p.radius as f32 == 0. {
        return Err(SceneError(
            "mesh transform proportional radius must be positive".into(),
        ));
    }
    if p.falloff == Falloff::Random && p.seed.is_none() {
        return Err(SceneError(
            "mesh transform random falloff requires an explicit seed".into(),
        ));
    }
    if p.falloff != Falloff::Random && p.seed.is_some() {
        return Err(SceneError(
            "mesh transform seed requires random falloff".into(),
        ));
    }
    if p.falloff != Falloff::Random && p.random_algorithm.is_some() {
        return Err(SceneError(
            "mesh transform random algorithm requires random falloff".into(),
        ));
    }
    if p.random_algorithm == Some(RandomAlgorithm::Blender52)
        && p.seed.is_some_and(|seed| seed > u32::MAX as u64)
    {
        return Err(SceneError(
            "mesh transform Blender random seed must fit u32".into(),
        ));
    }
    let project = |point: Vector| {
        if p.projected {
            let along = dot(point, context.view_axis);
            std::array::from_fn(|i| point[i] - context.view_axis[i] * along)
        } else {
            point
        }
    };
    let surface = if p.connected {
        Some(geodesic::calculate(
            context,
            request.max_components.saturating_mul(64),
        )?)
    } else {
        None
    };
    let tree = if surface.is_none() {
        let mut points: Vec<_> = context
            .world_positions
            .iter()
            .zip(&context.selected)
            .filter(|(_, s)| **s)
            .map(|(p, _)| project(*p))
            .collect();
        Tree::build(&mut points, 0)
    } else {
        None
    };
    let radius = p.radius as f32;
    let mut stream = Stream::new(p.random_algorithm, p.seed.unwrap_or(0));
    let mut result = vec![0.; context.positions.len()];
    for (i, value) in result.iter_mut().enumerate() {
        if !context.visible[i] {
            continue;
        }
        if context.selected[i] {
            *value = 1.;
            continue;
        }
        let distance = if let Some(surface) = &surface {
            if surface.values[i] == f32::MAX {
                continue;
            }
            surface.values[i]
        } else {
            let mut squared = f32::INFINITY;
            tree.as_ref()
                .expect("selected point tree")
                .nearest(project(context.world_positions[i]), &mut squared);
            squared.sqrt()
        };
        if !distance.is_finite() {
            return Err(SceneError(
                "mesh transform proportional distance exceeded finite f32 range".into(),
            ));
        }
        if distance > radius {
            continue;
        }
        let ratio = ((radius - distance) / radius).max(0.);
        *value = match p.falloff {
            Falloff::Smooth => (3. * ratio * ratio - 2. * ratio * ratio * ratio).min(1.),
            Falloff::Sphere => (2. * ratio - ratio * ratio).sqrt(),
            Falloff::Root => ratio.sqrt(),
            Falloff::Sharp => ratio * ratio,
            Falloff::Linear => ratio,
            Falloff::Constant => 1.,
            Falloff::Random => stream.next() * ratio,
            Falloff::InverseSquare => ratio * (2. - ratio),
        };
    }
    Ok(Influence {
        weights: result,
        origins: surface.map(|s| s.origins),
    })
}
