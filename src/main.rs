use std::path::PathBuf;

fn main() -> std::process::ExitCode {
    let mut args = std::env::args().skip(1);
    if args.next().as_deref() != Some("baseline") || args.next().as_deref() != Some("check") {
        eprintln!("Usage: formora baseline check [--root PATH] [--strict]");
        return std::process::ExitCode::from(64);
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
