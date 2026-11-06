use super::{Playback, math, render::Renderer};
use crate::scene::{Annotation, Command, Result, SceneError};
use crate::session::{ApplyRequest, Session};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use winit::application::ApplicationHandler;
use winit::dpi::{LogicalSize, PhysicalPosition};
use winit::event::{ElementState, Ime, MouseButton, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::keyboard::{Key, KeyCode, ModifiersState, NamedKey, PhysicalKey};
use winit::window::{Window, WindowId};

enum Event {
    Stop,
}
struct Draft {
    entity: String,
    position: [f64; 3],
    text: String,
}

struct App {
    session: Arc<Mutex<Session>>,
    playback: Playback,
    window: Option<Arc<Window>>,
    renderer: Option<Renderer>,
    cursor: Option<PhysicalPosition<f64>>,
    modifiers: ModifiersState,
    draft: Option<Draft>,
    composing: bool,
    last_frame: Instant,
    last_title: Instant,
    displayed_title: String,
    capture: PathBuf,
    capture_first: bool,
    failure: Option<SceneError>,
    last_error: String,
}

impl App {
    fn title(&mut self) {
        self.last_error.clear();
        let Some(window) = &self.window else {
            return;
        };
        let title = if let Some(draft) = &self.draft {
            format!(
                "Formora — Note: {}  |  Enter saves · Esc cancels",
                draft.text
            )
        } else {
            let door = self
                .playback
                .scene
                .doors
                .values()
                .next()
                .map(|d| {
                    format!(
                        "Door {:.0}% · {:.2}s  |  ",
                        d.progress * 100.0,
                        d.duration_seconds
                    )
                })
                .unwrap_or_default();
            let state = if self.playback.playing {
                "Pause"
            } else {
                "Play"
            };
            format!("Formora — {door}Click door · Space {state} · Shift+click note · S capture")
        };
        if title != self.displayed_title {
            window.set_title(&title);
            self.displayed_title = title;
        }
        self.last_title = Instant::now();
    }

    fn show_error(&mut self, error: SceneError) {
        self.playback.playing = false;
        if self.last_error != error.0 {
            eprintln!("Preview: {error}");
            self.last_error = error.0.clone();
        }
        if let Some(window) = &self.window {
            let title = format!("Formora — {error}");
            if title != self.displayed_title {
                window.set_title(&title);
                self.displayed_title = title;
            }
        }
    }

    fn click(&mut self) -> Result<()> {
        let Some(cursor) = self.cursor else {
            return Ok(());
        };
        let Some(renderer) = &self.renderer else {
            return Ok(());
        };
        let (origin, direction) = math::ray(
            &self.playback.scene,
            renderer.width,
            renderer.height,
            cursor.x,
            cursor.y,
        )?;
        if let Some(hit) = math::pick(&self.playback.scene, origin, direction)? {
            if self.modifiers.shift_key() {
                self.draft = Some(Draft {
                    entity: hit.entity,
                    position: hit.position.to_array(),
                    text: String::new(),
                });
                self.window
                    .as_ref()
                    .expect("window exists")
                    .set_ime_allowed(true);
            } else if let Some(door) = math::door_for_entity(&self.playback.scene, &hit.entity) {
                self.playback.toggle_door(&door)?;
            }
        }
        self.title();
        Ok(())
    }

    fn save_note(&mut self) -> Result<()> {
        let Some(draft) = &self.draft else {
            return Ok(());
        };
        if draft.text.trim().is_empty() {
            return Err(SceneError("Type a note, then press Enter.".into()));
        }
        {
            let mut session = self
                .session
                .lock()
                .map_err(|_| SceneError("scene session is unavailable".into()))?;
            let revision = session.scene().revision;
            session.apply(ApplyRequest {
                expected_revision: revision,
                commands: vec![Command::Annotate {
                    annotation: Annotation {
                        entity: Some(draft.entity.clone()),
                        position: draft.position,
                        text: draft.text.clone(),
                    },
                }],
            })?;
            self.playback.sync(session.scene())?;
        }
        self.draft = None;
        self.composing = false;
        self.window
            .as_ref()
            .expect("window exists")
            .set_ime_allowed(false);
        self.title();
        Ok(())
    }

    fn capture(&mut self) -> Result<()> {
        if let Some(renderer) = &self.renderer {
            renderer.capture(&self.playback.scene, &self.capture)?;
            eprintln!("Captured {}", self.capture.display());
        }
        Ok(())
    }

    fn frame(&mut self) -> Result<()> {
        {
            let session = self
                .session
                .lock()
                .map_err(|_| SceneError("scene session is unavailable".into()))?;
            if session.scene().revision != self.playback.scene.revision {
                self.last_error.clear();
            }
            self.playback.sync(session.scene())?;
        }
        let now = Instant::now();
        let delta = now.duration_since(self.last_frame).as_secs_f64();
        self.last_frame = now;
        self.playback.advance(delta)?;
        if let Some(renderer) = &mut self.renderer {
            renderer.draw(&self.playback.scene)?;
        }
        if self.capture_first {
            self.capture()?;
            self.capture_first = false;
        }
        if self.last_error.is_empty() && self.last_title.elapsed() > Duration::from_millis(200) {
            self.title();
        }
        Ok(())
    }
}

impl ApplicationHandler<Event> for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.window.is_some() {
            return;
        }
        let initialized = (|| -> Result<()> {
            let window = Arc::new(
                event_loop
                    .create_window(
                        Window::default_attributes()
                            .with_title("Formora")
                            .with_inner_size(LogicalSize::new(1280.0, 800.0)),
                    )
                    .map_err(|e| SceneError(e.to_string()))?,
            );
            let size = window.inner_size();
            let renderer = pollster::block_on(Renderer::new(
                Some(window.clone()),
                size.width.max(1),
                size.height.max(1),
            ))?;
            eprintln!("Preview GPU: {}", renderer.adapter);
            self.window = Some(window);
            self.renderer = Some(renderer);
            self.last_frame = Instant::now();
            self.title();
            Ok(())
        })();
        if let Err(error) = initialized {
            self.failure = Some(error);
            event_loop.exit();
        }
    }

    fn user_event(&mut self, event_loop: &ActiveEventLoop, _event: Event) {
        event_loop.exit();
    }

    fn window_event(
        &mut self,
        event_loop: &ActiveEventLoop,
        _window_id: WindowId,
        event: WindowEvent,
    ) {
        let result = match event {
            WindowEvent::CloseRequested => {
                event_loop.exit();
                Ok(())
            }
            WindowEvent::Resized(size) => {
                if let Some(renderer) = &mut self.renderer {
                    renderer.resize(size.width, size.height);
                }
                Ok(())
            }
            WindowEvent::CursorMoved { position, .. } => {
                self.cursor = Some(position);
                Ok(())
            }
            WindowEvent::ModifiersChanged(modifiers) => {
                self.modifiers = modifiers.state();
                Ok(())
            }
            WindowEvent::MouseInput {
                state: ElementState::Released,
                button: MouseButton::Left,
                ..
            } => self.click(),
            WindowEvent::RedrawRequested => self.frame(),
            WindowEvent::Ime(Ime::Preedit(text, _)) => {
                self.composing = !text.is_empty();
                Ok(())
            }
            WindowEvent::Ime(Ime::Commit(text)) => {
                if let Some(draft) = &mut self.draft {
                    draft.text.push_str(&text);
                }
                self.composing = false;
                self.title();
                Ok(())
            }
            WindowEvent::KeyboardInput { event, .. } if event.state == ElementState::Pressed => {
                if self.draft.is_some() {
                    match &event.logical_key {
                        _ if event.physical_key == PhysicalKey::Code(KeyCode::KeyV)
                            && (self.modifiers.super_key() || self.modifiers.control_key()) =>
                        {
                            match arboard::Clipboard::new()
                                .and_then(|mut clipboard| clipboard.get_text())
                            {
                                Ok(text) => {
                                    self.draft
                                        .as_mut()
                                        .expect("draft exists")
                                        .text
                                        .extend(text.chars().filter(|c| !c.is_control()));
                                    self.composing = false;
                                    self.title();
                                    Ok(())
                                }
                                Err(error) => {
                                    Err(SceneError(format!("Cannot paste note: {error}")))
                                }
                            }
                        }
                        Key::Named(NamedKey::Enter) if !self.composing => self.save_note(),
                        Key::Named(NamedKey::Escape) => {
                            self.draft = None;
                            self.composing = false;
                            self.window
                                .as_ref()
                                .expect("window exists")
                                .set_ime_allowed(false);
                            self.title();
                            Ok(())
                        }
                        Key::Named(NamedKey::Backspace) if !self.composing => {
                            self.draft.as_mut().expect("draft exists").text.pop();
                            self.title();
                            Ok(())
                        }
                        _ => {
                            if !self.composing
                                && !self.modifiers.control_key()
                                && !self.modifiers.super_key()
                            {
                                if let Some(text) = event.text {
                                    self.draft
                                        .as_mut()
                                        .expect("draft exists")
                                        .text
                                        .extend(text.chars().filter(|c| !c.is_control()));
                                }
                            }
                            self.title();
                            Ok(())
                        }
                    }
                } else {
                    match &event.logical_key {
                        Key::Named(NamedKey::Space) => {
                            self.playback.playing = !self.playback.playing;
                            self.title();
                            Ok(())
                        }
                        Key::Named(NamedKey::Escape) => {
                            event_loop.exit();
                            Ok(())
                        }
                        _ if event.physical_key == PhysicalKey::Code(KeyCode::KeyS) => {
                            self.capture()
                        }
                        _ if event.physical_key == PhysicalKey::Code(KeyCode::KeyR) => {
                            match self.session.lock() {
                                Ok(session) => {
                                    self.playback = Playback::new(session.scene());
                                    Ok(())
                                }
                                Err(_) => Err(SceneError("scene session is unavailable".into())),
                            }
                        }
                        _ => Ok(()),
                    }
                }
            }
            _ => Ok(()),
        };
        if let Err(error) = result {
            self.show_error(error);
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        event_loop.set_control_flow(ControlFlow::WaitUntil(
            Instant::now() + Duration::from_millis(16),
        ));
        if let Some(window) = &self.window {
            window.request_redraw();
        }
    }
}

pub fn run(session: Session, mcp: bool, capture: Option<PathBuf>) -> Result<()> {
    let event_loop = EventLoop::<Event>::with_user_event()
        .build()
        .map_err(|e| SceneError(e.to_string()))?;
    let playback = Playback::new(session.scene());
    let shared = Arc::new(Mutex::new(session));
    if mcp {
        let session = shared.clone();
        let proxy = event_loop.create_proxy();
        std::thread::spawn(move || {
            let stdin = std::io::stdin();
            let stdout = std::io::stdout();
            if let Err(error) = crate::agent::mcp_serve_shared(session, stdin.lock(), stdout.lock())
            {
                eprintln!("MCP: {error}");
            }
            let _ = proxy.send_event(Event::Stop);
        });
    }
    let now = Instant::now();
    let mut app = App {
        session: shared,
        playback,
        window: None,
        renderer: None,
        cursor: None,
        modifiers: ModifiersState::empty(),
        draft: None,
        composing: false,
        last_frame: now,
        last_title: now,
        displayed_title: String::new(),
        capture_first: capture.is_some(),
        capture: capture.unwrap_or_else(|| std::env::temp_dir().join("formora-preview.png")),
        failure: None,
        last_error: String::new(),
    };
    event_loop
        .run_app(&mut app)
        .map_err(|e| SceneError(e.to_string()))?;
    match app.failure {
        Some(error) => Err(error),
        None => Ok(()),
    }
}
