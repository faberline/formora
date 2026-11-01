// Actual Apple loader and native renderer. No SceneKit, Blender or alternate parser.
#if os(macOS)
import AppKit
typealias PlatformColor = NSColor
#else
import UIKit
typealias PlatformColor = UIColor
#endif
import CryptoKit
import Foundation
import Metal
import RealityKit
import simd

func vector(_ p: SIMD3<Float>) -> [Float] { [p.x, p.y, p.z] }
func matrix(_ m: simd_float4x4) -> [[Float]] {
    (0..<4).map { r in (0..<4).map { c in m[c][r] } }
}
func point(_ m: simd_float4x4, _ p: SIMD3<Float>) -> [Float] {
    let v = m * SIMD4<Float>(p, 1)
    return [v.x / v.w, v.y / v.w, v.z / v.w]
}
func hash(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
@MainActor func color(_ c: PlatformColor) throws -> [Float] {
    guard let space=CGColorSpace(name:CGColorSpace.extendedLinearSRGB),
          let converted=c.cgColor.converted(to:space,intent:.defaultIntent,options:nil),
          let components=converted.components,components.count==4 else { throw Failure.message("No linear RGB material color") }
    return components.map(Float.init)
}
enum Failure: Error { case message(String) }
@MainActor func material(_ value: any Material) throws -> [String: Any] {
    if let m = value as? PhysicallyBasedMaterial {
        guard m.baseColor.texture == nil, m.roughness.texture == nil, m.metallic.texture == nil else {
            throw Failure.message("Unexpected texture in static material")
        }
        return ["type":"PhysicallyBasedMaterial", "base_color":try color(m.baseColor.tint),
                "roughness":m.roughness.scale, "metallic":m.metallic.scale,
                "blending":String(describing:m.blending)]
    }
    if let m = value as? SimpleMaterial {
        guard case .float(let roughness) = m.roughness, case .float(let metallic) = m.metallic,
              m.color.texture == nil else { throw Failure.message("Unexpected simple material texture") }
        return ["type":"SimpleMaterial", "base_color":try color(m.color.tint), "roughness":roughness, "metallic":metallic]
    }
    return ["type":String(describing:type(of:value)),"numeric_values_available":false]
}
@MainActor func inspect(_ entity: Entity, parentPath: String = "") throws -> [[String: Any]] {
    let path = parentPath + "/" + entity.name
    var node: [String: Any] = ["name":entity.name,"path":path,"parent":parentPath,
                               "local_matrix":matrix(entity.transform.matrix),
                               "world_matrix":matrix(entity.transformMatrix(relativeTo:nil))]
    if let component = entity.components[ModelComponent.self] {
        let contents = component.mesh.contents
        var parts = [[String: Any]]()
        for instance in contents.instances {
            guard let model = contents.models.first(where: { $0.id == instance.model }) else { throw Failure.message("Missing mesh model") }
            for part in model.parts {
                guard let indices = part.triangleIndices else { throw Failure.message("No triangle buffer") }
                let positions = Array(part.positions)
                let index = Array(indices)
                guard index.count % 3 == 0, index.allSatisfy({ Int($0) < positions.count }),
                      part.materialIndex >= 0, part.materialIndex < component.materials.count else { throw Failure.message("Invalid loaded mesh buffer") }
                let world = entity.transformMatrix(relativeTo:nil) * instance.transform
                parts.append(["instance":instance.id,"model":model.id,"part":part.id,
                              "instance_matrix":matrix(instance.transform),"material_index":part.materialIndex,
                              "positions":positions.map(vector),"indices":index,
                              "world_positions":positions.map { point(world,$0) },
                              "normals":part.normals.map { Array($0).map(vector) } ?? [],
                              "uv":part.textureCoordinates.map { Array($0).map { [$0.x,$0.y] } } ?? []])
            }
        }
        node["parts"] = parts
        node["materials"] = try component.materials.map(material)
    }
    return [node] + (try entity.children.flatMap { try inspect($0,parentPath:path) })
}

#if os(macOS)
@MainActor final class Captures {
    let view: ARView
    let window: NSWindow
    let camera = PerspectiveCamera()
    let dir: URL
    let center: SIMD3<Float>
    let radius: Float
    var index = 0
    var receipts = [[String: Any]]()
    let directions: [SIMD3<Float>] = [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1],[1,0.7,1],[-1,0.6,-1]]
    init(root: Entity, dir: URL) {
        self.dir = dir
        view = ARView(frame:NSRect(x:0,y:0,width:800,height:800))
        window = NSWindow(contentRect:view.frame,styleMask:[.titled,.closable],backing:.buffered,defer:false)
        window.title = "Formora native USD validation"
        window.contentView = view
        view.environment.background = .color(NSColor(white:0.12,alpha:1))
        let anchor = AnchorEntity(world:.zero)
        anchor.addChild(root)
        anchor.addChild(camera)
        let key = DirectionalLight()
        key.light.intensity = 2500
        key.look(at:.zero,from:[3,5,4],relativeTo:nil)
        anchor.addChild(key)
        let fill = DirectionalLight()
        fill.light.intensity = 1500
        fill.look(at:.zero,from:[-3,-4,-2],relativeTo:nil)
        anchor.addChild(fill)
        view.scene.anchors.append(anchor)
        let bounds = root.visualBounds(relativeTo:nil)
        center = bounds.center
        radius = max(simd_length(bounds.extents)*1.8,0.5)
        camera.camera.fieldOfViewInDegrees = 45
        window.makeKeyAndOrderFront(nil)
    }
    func next() {
        if index == directions.count {
            do {
                let data = try JSONSerialization.data(withJSONObject:receipts,options:[.prettyPrinted,.sortedKeys])
                try data.write(to:dir.appendingPathComponent("captures.json"),options:.withoutOverwriting)
                NSApplication.shared.stop(nil)
                // Wake the AppKit event loop so stop is observed.
                if let event = NSEvent.otherEvent(with:.applicationDefined,location:.zero,modifierFlags:[],timestamp:0,windowNumber:0,context:nil,subtype:0,data1:0,data2:0) { NSApplication.shared.postEvent(event,atStart:false) }
            } catch { fputs("\(error)\n",stderr); exit(1) }
            return
        }
        let number = index
        let direction = simd_normalize(directions[number])
        let up: SIMD3<Float> = abs(direction.y)>0.99 ? [0,0,1] : [0,1,0]
        camera.look(at:center,from:center+direction*radius,upVector:up,relativeTo:nil)
        DispatchQueue.main.asyncAfter(deadline:.now()+0.8) { [self] in
            view.snapshot(saveToHDR:false) { [self] image in
                do {
                    guard let image, let tiff=image.tiffRepresentation,
                          let bitmap=NSBitmapImageRep(data:tiff), let data=bitmap.representation(using:.png,properties:[:]) else { throw Failure.message("Native GPU snapshot failed") }
                    let name=String(format:"view-%02d.png",number)
                    try data.write(to:dir.appendingPathComponent(name),options:.withoutOverwriting)
                    receipts.append(["file":name,"sha256":hash(data),"camera_world_matrix":matrix(camera.transformMatrix(relativeTo:nil)),"width":bitmap.pixelsWide,"height":bitmap.pixelsHigh])
                    index += 1
                    next()
                } catch { fputs("\(error)\n",stderr); exit(1) }
            }
        }
    }
}

@main struct Inspector {
    @MainActor static func main() {
        do {
            guard CommandLine.arguments.count == 3 || CommandLine.arguments.count == 4 else { throw Failure.message("usage: apple-static-usd INPUT.usda NEW.json [NEW_CAPTURE_DIR]") }
            let input = URL(fileURLWithPath:CommandLine.arguments[1])
            let output = URL(fileURLWithPath:CommandLine.arguments[2])
            let data = try Data(contentsOf:input)
            let start = DispatchTime.now().uptimeNanoseconds
            let root = try Entity.load(contentsOf:input)
            let nodes = try inspect(root)
            guard nodes.contains(where:{$0["parts"] != nil}) else { throw Failure.message("Apple loader returned no mesh") }
            let report:[String:Any] = ["loader":"RealityKit.Entity.load(contentsOf:)","pid":ProcessInfo.processInfo.processIdentifier,
                                      "os":ProcessInfo.processInfo.operatingSystemVersionString,"input_sha256":hash(data),
                                      "elapsed_ns":DispatchTime.now().uptimeNanoseconds-start,"metal_device":MTLCreateSystemDefaultDevice()?.name ?? "unavailable","nodes":nodes]
            try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]).write(to:output,options:.withoutOverwriting)
            if CommandLine.arguments.count == 4 {
                let dir=URL(fileURLWithPath:CommandLine.arguments[3],isDirectory:true)
                try FileManager.default.createDirectory(at:dir,withIntermediateDirectories:false)
                let app=NSApplication.shared
                app.setActivationPolicy(.regular)
                let captures=Captures(root:root,dir:dir)
                captures.next()
                app.run()
                withExtendedLifetime(captures) {}
            }
        } catch { fputs("\(error)\n",stderr); exit(1) }
    }
}

#endif
