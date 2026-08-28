"""Static asset serving for the OpsBench 3D pipeline visualization page."""

from __future__ import annotations

PIPELINE_STAGES: tuple[str, ...] = (
    "Plan",
    "Code",
    "Build",
    "Test",
    "Release",
    "Deploy",
    "Operate",
    "Monitor",
)


def render_pipeline_html() -> str:
    """Render a standalone animated 3D DevOps pipeline loop page (Three.js, CDN-loaded)."""
    stage_labels = ", ".join(f'"{stage}"' for stage in PIPELINE_STAGES)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpsBench Pipeline</title>
    <style>
        body {{
            margin: 0;
            background: #0f172a;
            overflow: hidden;
            font-family: system-ui, -apple-system, sans-serif;
        }}
        #label {{
            position: absolute;
            top: 1.5rem;
            left: 50%;
            transform: translateX(-50%);
            color: #f8fafc;
            font-size: 1.25rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            opacity: 0.85;
        }}
        canvas {{ display: block; }}
    </style>
</head>
<body>
    <div id="label">OpsBench DevOps Pipeline</div>
    <script type="module">
        import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

        const stages = [{stage_labels}];

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(
            60, window.innerWidth / window.innerHeight, 0.1, 100
        );
        camera.position.set(0, 3, 9);

        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        scene.add(new THREE.AmbientLight(0xffffff, 0.6));
        const pointLight = new THREE.PointLight(0x38bdf8, 1.5, 50);
        pointLight.position.set(0, 5, 5);
        scene.add(pointLight);

        const loopGroup = new THREE.Group();
        scene.add(loopGroup);

        const radius = 4;
        const nodeGeometry = new THREE.SphereGeometry(0.35, 32, 32);
        const nodeMaterial = new THREE.MeshStandardMaterial({{ color: 0x38bdf8, emissive: 0x0f172a }});

        stages.forEach((stage, index) => {{
            const angle = (index / stages.length) * Math.PI * 2;
            const node = new THREE.Mesh(nodeGeometry, nodeMaterial.clone());
            node.position.set(Math.cos(angle) * radius, Math.sin(angle) * radius, 0);
            node.userData.stage = stage;
            loopGroup.add(node);
        }});

        const curvePoints = stages.map((_, index) => {{
            const angle = (index / stages.length) * Math.PI * 2;
            return new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, 0);
        }});
        curvePoints.push(curvePoints[0]);
        const loopCurve = new THREE.CatmullRomCurve3(curvePoints, true);
        const tubeGeometry = new THREE.TubeGeometry(loopCurve, 200, 0.05, 8, true);
        const tubeMaterial = new THREE.MeshStandardMaterial({{ color: 0x22c55e, emissive: 0x14532d }});
        loopGroup.add(new THREE.Mesh(tubeGeometry, tubeMaterial));

        function animate() {{
            requestAnimationFrame(animate);
            loopGroup.rotation.z += 0.004;
            loopGroup.rotation.x = Math.sin(Date.now() * 0.0002) * 0.3;
            renderer.render(scene, camera);
        }}
        animate();

        window.addEventListener("resize", () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});
    </script>
</body>
</html>
"""
