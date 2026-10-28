fn main() -> Result<(), Box<dyn std::error::Error>> {
    let scene = formora::scene::room_demo()?;
    println!("{}", serde_json::to_string_pretty(&scene)?);
    Ok(())
}
