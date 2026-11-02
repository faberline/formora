//! Native result preview. Authoring remains in the shared scene session.
pub use crate::geometry as math;
mod render;
mod window;

pub use render::{PreparedScene, Renderer, render_png};
pub use window::run;

use crate::scene::{Command, Result, Scene};

pub struct Playback {
    authored: Scene,
    pub scene: Scene,
    pub playing: bool,
}

impl Playback {
    pub fn new(scene: &Scene) -> Self {
        Self {
            authored: scene.clone(),
            scene: scene.clone(),
            playing: false,
        }
    }

    pub fn sync(&mut self, authored: &Scene) -> Result<()> {
        if authored.revision == self.authored.revision {
            return Ok(());
        }
        let mut next = authored.clone();
        for (id, door) in &mut next.doors {
            if let (Some(previous), Some(live)) =
                (self.authored.doors.get(id), self.scene.doors.get(id))
            {
                if door.entity == previous.entity {
                    if door.progress == previous.progress {
                        door.progress = live.progress;
                    }
                    if door.target_open == previous.target_open
                        && door.trigger_revision == previous.trigger_revision
                    {
                        door.target_open = live.target_open;
                    }
                    next.entities
                        .get_mut(&door.entity)
                        .expect("authored scene is valid")
                        .transform
                        .rotation = door.rotation().into();
                }
            }
        }
        if next.time_seconds == self.authored.time_seconds {
            next.time_seconds = self.scene.time_seconds;
        }
        next.validate()?;
        self.authored = authored.clone();
        self.scene = next;
        Ok(())
    }

    pub fn advance(&mut self, seconds: f64) -> Result<()> {
        if self.playing {
            self.scene = self.scene.simulated(&[Command::Advance { seconds }])?;
        }
        Ok(())
    }

    pub fn toggle_door(&mut self, id: &str) -> Result<()> {
        let open = !self
            .scene
            .doors
            .get(id)
            .ok_or_else(|| crate::scene::SceneError(format!("unknown door: {id}")))?
            .target_open;
        self.scene = self.scene.simulated(&[Command::TriggerDoor {
            id: id.into(),
            open,
        }])?;
        self.playing = true;
        Ok(())
    }
}
