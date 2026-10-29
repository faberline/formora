use std::collections::BTreeMap;
use std::io::Read;
use std::path::{Path, PathBuf};

fn usage(message: &str) -> std::process::ExitCode {
    eprintln!(
        "{message}\nUsage:\n  formora baseline check [--root PATH] [--strict]\n  formora scene init --scene PATH [--demo-room]\n  formora scene inspect --scene PATH [--entity ID [--world] | --mesh-asset ID [--tessellate] [--selection-topology] [--normals]]\n  formora scene apply --scene PATH --request FILE|-\n  formora scene serve --scene PATH\n  formora scene schema\n  formora mcp --scene PATH [--preview] [--capture PNG]\n  formora preview --scene PATH [--capture PNG]\n  formora render --scene PATH --output PNG [--width N] [--height N]"
    );
    std::process::ExitCode::from(64)
}

fn options(
    mut args: impl Iterator<Item = String>,
    allowed: &[&str],
) -> Result<BTreeMap<String, String>, String> {
    let mut values = BTreeMap::new();
    while let Some(key) = args.next() {
        if !allowed.contains(&key.as_str()) {
            return Err(format!("unknown option: {key}"));
        }
        if values.contains_key(&key) {
            return Err(format!("duplicate option: {key}"));
        }
        let value = if [
            "--demo-room",
            "--preview",
            "--tessellate",
            "--selection-topology",
            "--normals",
            "--world",
        ]
        .contains(&key.as_str())
        {
            String::new()
        } else {
            args.next()
                .filter(|s| !s.starts_with("--"))
                .ok_or_else(|| format!("{key} requires a value"))?
        };
        values.insert(key, value);
    }
    Ok(values)
}

fn scene_cli(action: &str, args: impl Iterator<Item = String>) -> std::process::ExitCode {
    let allowed: &[&str] = match action {
        "init" => &["--scene", "--demo-room"],
        "inspect" => &[
            "--scene",
            "--entity",
            "--mesh-asset",
            "--tessellate",
            "--selection-topology",
            "--normals",
            "--world",
        ],
        "apply" => &["--scene", "--request"],
        "serve" => &["--scene"],
        "mcp" => &["--scene", "--preview", "--capture"],
        "preview" => &["--scene", "--capture"],
        "render" => &["--scene", "--output", "--width", "--height"],
        "schema" => &[],
        _ => return usage("unknown scene action"),
    };
    let options = match options(args, allowed) {
        Ok(options) => options,
        Err(error) => return usage(&error),
    };
    if action == "schema" {
        println!(
            "{}",
            serde_json::to_string_pretty(&formora::agent::tools()).expect("schemas serialize")
        );
        return std::process::ExitCode::SUCCESS;
    }
    let Some(path) = options.get("--scene") else {
        return usage("--scene is required");
    };
    if action == "apply" && !options.contains_key("--request") {
        return usage("--request is required");
    }
    if action == "render" && !options.contains_key("--output") {
        return usage("--output is required");
    }
    if action == "mcp" && options.contains_key("--capture") && !options.contains_key("--preview") {
        return usage("--capture requires --preview");
    }
    let result = (|| -> Result<Option<serde_json::Value>, String> {
        let map_err = |e: formora::scene::SceneError| e.to_string();
        match action {
            "preview" | "render" => {
                #[cfg(feature = "preview")]
                {
                    if action == "preview" {
                        let session =
                            formora::session::Session::open(Path::new(path)).map_err(map_err)?;
                        formora::preview::run(
                            session,
                            false,
                            options.get("--capture").map(PathBuf::from),
                        )
                        .map_err(map_err)?;
                        Ok(None)
                    } else {
                        let dimension = |key: &str, default| -> Result<u32, String> {
                            options
                                .get(key)
                                .map(|v| {
                                    v.parse::<u32>()
                                        .map_err(|_| format!("{key} must be a positive integer"))
                                })
                                .unwrap_or(Ok(default))
                        };
                        let width = dimension("--width", 1280)?;
                        let height = dimension("--height", 800)?;
                        let scene =
                            formora::scene::Scene::load(Path::new(path)).map_err(map_err)?;
                        let adapter = formora::preview::render_png(
                            &scene,
                            Path::new(&options["--output"]),
                            width,
                            height,
                        )
                        .map_err(map_err)?;
                        Ok(Some(
                            serde_json::json!({"output":options["--output"],"width":width,"height":height,"gpu":adapter}),
                        ))
                    }
                }
                #[cfg(not(feature = "preview"))]
                {
                    Err("preview support is not enabled; build with --features preview".into())
                }
            }
            "init" => {
                let scene = if options.contains_key("--demo-room") {
                    formora::scene::room_demo().map_err(map_err)?
                } else {
                    formora::scene::Scene::default()
                };
                let session =
                    formora::session::Session::create(Path::new(path), scene).map_err(map_err)?;
                Ok(Some(
                    serde_json::json!({"revision":session.scene().revision}),
                ))
            }
            "inspect" => {
                let scene = formora::scene::Scene::load(Path::new(path)).map_err(map_err)?;
                let value = formora::session::InspectRequest {
                    entity: options.get("--entity").cloned(),
                    mesh_asset: options.get("--mesh-asset").cloned(),
                    tessellate: options.contains_key("--tessellate"),
                    selection_topology: options.contains_key("--selection-topology"),
                    normals: options.contains_key("--normals"),
                    world: options.contains_key("--world"),
                }
                .inspect(&scene)
                .map_err(map_err)?;
                Ok(Some(value))
            }
            "apply" => {
                let request_path = &options["--request"];
                let mut bytes = Vec::new();
                let mut input: Box<dyn Read> = if request_path == "-" {
                    Box::new(std::io::stdin())
                } else {
                    Box::new(std::fs::File::open(request_path).map_err(|e| e.to_string())?)
                };
                input
                    .by_ref()
                    .take(16 * 1024 * 1024 + 1)
                    .read_to_end(&mut bytes)
                    .map_err(|e| e.to_string())?;
                if bytes.len() > 16 * 1024 * 1024 {
                    return Err("request exceeds 16 MiB".into());
                }
                let request = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
                let mut session =
                    formora::session::Session::open(Path::new(path)).map_err(map_err)?;
                let result = session.apply_with_result(request).map_err(map_err)?;
                Ok(Some(serde_json::json!(result)))
            }
            "serve" | "mcp" => {
                let mut session =
                    formora::session::Session::open(Path::new(path)).map_err(map_err)?;
                if options.contains_key("--preview") {
                    #[cfg(feature = "preview")]
                    {
                        formora::preview::run(
                            session,
                            true,
                            options.get("--capture").map(PathBuf::from),
                        )
                        .map_err(map_err)?;
                        return Ok(None);
                    }
                    #[cfg(not(feature = "preview"))]
                    {
                        return Err(
                            "preview support is not enabled; build with --features preview".into(),
                        );
                    }
                }
                let stdin = std::io::stdin();
                let stdout = std::io::stdout();
                if action == "mcp" {
                    formora::agent::mcp_serve(&mut session, stdin.lock(), stdout.lock())
                } else {
                    formora::agent::native_serve(&mut session, stdin.lock(), stdout.lock())
                }
                .map_err(|e| e.to_string())?;
                Ok(None)
            }
            _ => unreachable!(),
        }
    })();
    match result {
        Ok(Some(value)) => {
            println!("{value}");
            std::process::ExitCode::SUCCESS
        }
        Ok(None) => std::process::ExitCode::SUCCESS,
        Err(error) => {
            if action == "mcp" {
                eprintln!("{error}");
            } else {
                println!("{}", serde_json::json!({"error":error}));
            }
            std::process::ExitCode::from(1)
        }
    }
}

fn main() -> std::process::ExitCode {
    let mut args = std::env::args().skip(1);
    match args.next().as_deref() {
        Some("scene") => {
            return match args.next() {
                Some(action) => scene_cli(&action, args),
                None => usage("scene action is required"),
            };
        }
        Some("mcp") => return scene_cli("mcp", args),
        Some("preview") => return scene_cli("preview", args),
        Some("render") => return scene_cli("render", args),
        Some("baseline") if args.next().as_deref() == Some("check") => {}
        _ => return usage("command is required"),
    }
    let mut root = PathBuf::from(".");
    let mut strict = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--root" => match args.next() {
                Some(path) => root = path.into(),
                None => {
                    eprintln!("--root requires a path");
                    return std::process::ExitCode::from(64);
                }
            },
            "--strict" => strict = true,
            _ => {
                eprintln!("Unknown argument: {arg}");
                return std::process::ExitCode::from(64);
            }
        }
    }
    match formora::baseline::check(&root) {
        Ok(report) => {
            let exit = if !report.structurally_valid {
                1
            } else if strict && !report.baseline_ready {
                2
            } else {
                0
            };
            println!(
                "{}",
                serde_json::to_string_pretty(&report).expect("report is serializable")
            );
            std::process::ExitCode::from(exit)
        }
        Err(error) => {
            println!(
                "{}",
                serde_json::json!({"structurally_valid":false,"baseline_ready":false,"product_acceptance":"unrun","error":error})
            );
            std::process::ExitCode::from(1)
        }
    }
}
