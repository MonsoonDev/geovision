const AXES = [
  { id: "+x", label: "X", math: [1, 0, 0], color: "#b4534a", sign: 1 },
  { id: "+y", label: "Y", math: [0, 1, 0], color: "#3f7d4e", sign: 1 },
  { id: "+z", label: "Z", math: [0, 0, 1], color: "#2f5da8", sign: 1 },
  { id: "-x", label: "", math: [-1, 0, 0], color: "#b4534a", sign: -1 },
  { id: "-y", label: "", math: [0, -1, 0], color: "#3f7d4e", sign: -1 },
  { id: "-z", label: "", math: [0, 0, -1], color: "#2f5da8", sign: -1 },
];

const CX = 48;
const CY = 48;
const REACH = 32;

function toThree(point) {
  return [point[0], point[2] || 0, point[1]];
}

function is3d(state) {
  return !!(state.scene && state.scene.view && state.scene.view.mode === "3d");
}

export function initCamera({ state, gfx, draw2d, computeBounds, renderFrame }) {
  const gizmo = document.querySelector("#gizmo");
  const dock = document.querySelector("#camera-dock");
  let orbit = null;
  let tips = [];

  function project(math) {
    if (is3d(state) && gfx.ready) {
      const THREE = gfx.THREE;
      const axis = new THREE.Vector3(...toThree(math)).normalize();
      const inverse = gfx.camera.quaternion.clone().invert();
      axis.applyQuaternion(inverse);
      return { x: CX + axis.x * REACH, y: CY - axis.y * REACH, depth: axis.z };
    }
    return { x: CX + math[0] * REACH, y: CY - math[1] * REACH, depth: math[2] || 0 };
  }

  function paint() {
    const nodes = [];
    tips = AXES.map((axis) => {
      const at = project(axis.math);
      return { ...axis, ...at };
    }).sort((a, b) => a.depth - b.depth);

    for (const axis of tips) {
      const faded = !is3d(state) && axis.math[2];
      const opacity = faded ? 0.22 : axis.sign < 0 ? 0.55 : 1;
      const r = axis.sign < 0 ? 5.5 : 8;
      nodes.push(
        `<line x1="${CX}" y1="${CY}" x2="${axis.x}" y2="${axis.y}" stroke="${axis.color}" stroke-width="${
          axis.sign < 0 ? 1.4 : 2.2
        }" stroke-linecap="round" opacity="${opacity}" />`
      );
      nodes.push(
        `<circle data-axis="${axis.id}" cx="${axis.x}" cy="${axis.y}" r="${r}" fill="${
          axis.sign < 0 ? "var(--panel)" : axis.color
        }" stroke="${axis.color}" stroke-width="1.6" opacity="${opacity}" />`
      );
      if (axis.label) {
        nodes.push(
          `<text data-axis="${axis.id}" x="${axis.x}" y="${axis.y}" fill="${
            axis.sign < 0 ? axis.color : "#fff"
          }" opacity="${opacity}">${axis.label}</text>`
        );
      }
    }
    gizmo.innerHTML = nodes.join("");
  }

  function lookAlong(math) {
    if (!is3d(state) || !gfx.ready) return;
    const THREE = gfx.THREE;
    const target = gfx.controls.target.clone();
    const distance = Math.max(0.5, gfx.camera.position.distanceTo(target));
    const direction = new THREE.Vector3(...toThree(math)).normalize();
    gfx.camera.position.copy(target).add(direction.multiplyScalar(distance));
    gfx.camera.up.set(0, 1, 0);
    gfx.controls.update();
    renderFrame();
    paint();
  }

  function hitAxis(event) {
    const matrix = gizmo.getScreenCTM();
    if (!matrix) return null;
    const point = gizmo.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const local = point.matrixTransform(matrix.inverse());
    let best = null;
    let bestDistance = 12;
    for (const axis of tips) {
      if (!is3d(state) && axis.math[2]) continue;
      const distance = Math.hypot(local.x - axis.x, local.y - axis.y);
      if (distance < bestDistance) {
        best = axis;
        bestDistance = distance;
      }
    }
    return best;
  }

  function zoom3d(factor) {
    if (!gfx.ready) return;
    const target = gfx.controls.target;
    const offset = gfx.camera.position.clone().sub(target);
    offset.multiplyScalar(factor);
    if (offset.length() < 0.4) offset.setLength(0.4);
    if (offset.length() > 400) offset.setLength(400);
    gfx.camera.position.copy(target).add(offset);
    gfx.controls.update();
    renderFrame();
    paint();
  }

  function zoom2d(factor) {
    if (!state.scene) return;
    const b = state.bounds;
    const mx = (b.minX + b.maxX) / 2;
    const my = (b.minY + b.maxY) / 2;
    state.bounds = {
      minX: mx - (mx - b.minX) * factor,
      maxX: mx + (b.maxX - mx) * factor,
      minY: my - (my - b.minY) * factor,
      maxY: my + (b.maxY - my) * factor,
    };
    draw2d(state.scene);
  }

  function resetCamera() {
    if (!state.scene) return;
    if (is3d(state) && gfx.ready) {
      const cam = (state.scene.view && state.scene.view.camera) || {};
      const position = cam.position || [6, -8, 5];
      const target = cam.target || [0, 0, 0];
      gfx.camera.position.set(...toThree(position));
      gfx.controls.target.set(...toThree(target));
      gfx.controls.update();
      state.camKey = JSON.stringify(cam);
      renderFrame();
      paint();
      return;
    }
    state.bounds = computeBounds(state.scene);
    draw2d(state.scene);
  }

  function locked() {
    return !!state.editing;
  }

  gizmo.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || locked()) return;
    const axis = hitAxis(event);
    if (axis && is3d(state)) {
      lookAlong(axis.math);
      return;
    }
    if (!is3d(state) || !gfx.ready) return;
    orbit = { x: event.clientX, y: event.clientY };
    gizmo.setPointerCapture(event.pointerId);
  });

  gizmo.addEventListener("pointermove", (event) => {
    if (!orbit || !gfx.ready || locked()) return;
    const THREE = gfx.THREE;
    const dx = event.clientX - orbit.x;
    const dy = event.clientY - orbit.y;
    orbit = { x: event.clientX, y: event.clientY };
    const offset = gfx.camera.position.clone().sub(gfx.controls.target);
    const spherical = new THREE.Spherical().setFromVector3(offset);
    spherical.theta -= dx * 0.012;
    spherical.phi = Math.min(Math.PI - 0.04, Math.max(0.04, spherical.phi - dy * 0.012));
    offset.setFromSpherical(spherical);
    gfx.camera.position.copy(gfx.controls.target).add(offset);
    gfx.controls.update();
    renderFrame();
    paint();
  });

  gizmo.addEventListener("pointerup", () => {
    orbit = null;
  });
  gizmo.addEventListener("pointercancel", () => {
    orbit = null;
  });

  document.querySelector("#cam-in").addEventListener("click", () => {
    if (locked()) return;
    if (is3d(state)) zoom3d(0.82);
    else zoom2d(0.82);
  });
  document.querySelector("#cam-out").addEventListener("click", () => {
    if (locked()) return;
    if (is3d(state)) zoom3d(1.22);
    else zoom2d(1.22);
  });
  document.querySelector("#cam-home").addEventListener("click", () => {
    if (locked()) return;
    resetCamera();
  });

  dock.addEventListener("wheel", (event) => {
    event.preventDefault();
    if (locked()) return;
    const inward = event.deltaY < 0;
    if (is3d(state)) zoom3d(inward ? 0.9 : 1.1);
    else zoom2d(inward ? 0.9 : 1.1);
  }, { passive: false });

  state.updateGizmo = paint;
  paint();
}
