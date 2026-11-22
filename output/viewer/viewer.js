// Docker Drone 3D viewer + animation of the full dock / flight cycle (three.js, PBR materials).
// Models come from cad/export_viewer.py (CAD in mm; GLB files are already Y-up: three(x, y, z) = CAD(x, z, -y)).
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const cfg = await (await fetch("viewer_config.json")).json();
const XH = cfg.hinge_x, ZH = cfg.hinge_z, PARK = cfg.pusher_park, XC = cfg.pusher_x_centred, YC = cfg.pusher_y_centred;
const ZDRONE = cfg.drone_on_deck_z, ZDECK = cfg.z_deck;

// ------------------------------------------------------------------ renderer, scene, camera
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
{
  const c = document.createElement("canvas"); c.width = 4; c.height = 512;
  const g = c.getContext("2d"), grd = g.createLinearGradient(0, 0, 0, 512);
  grd.addColorStop(0, "#5f9bd6"); grd.addColorStop(0.62, "#b9d5ec"); grd.addColorStop(1, "#e4edf3");
  g.fillStyle = grd; g.fillRect(0, 0, 4, 512);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; scene.background = t;
  scene.fog = new THREE.Fog(0xdde8f0, 12000, 42000);
}
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;

const camera = new THREE.PerspectiveCamera(35, innerWidth / innerHeight, 10, 80000);
camera.position.set(1500, 1150, 1700);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 380, 0);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.495;
controls.minDistance = 250;
controls.maxDistance = 14000;

scene.add(new THREE.HemisphereLight(0xcfe3ff, 0x5d7442, 0.6));
const sun = new THREE.DirectionalLight(0xfff1dc, 2.9);
sun.position.set(1800, 3400, 1300);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
Object.assign(sun.shadow.camera, { left: -2800, right: 2800, top: 2800, bottom: -2800, near: 200, far: 9000 });
sun.shadow.bias = -0.0003;
sun.shadow.normalBias = 1.2;
scene.add(sun);
const rim = new THREE.DirectionalLight(0xdde7ff, 0.9);
rim.position.set(-2600, 1600, -2200);
scene.add(rim);

function noiseTexture(base, spread, n = 256, reps = 1) {        // procedural grass / concrete
  const c = document.createElement("canvas"); c.width = c.height = n;
  const g = c.getContext("2d"), img = g.createImageData(n, n);
  for (let i = 0; i < n * n; i++) {
    const k = (Math.random() - 0.5) * spread, j = (Math.random() < 0.08 ? -1 : 0) * spread * 0.8;
    img.data[i * 4] = base[0] + k + j; img.data[i * 4 + 1] = base[1] + k * 1.2 + j; img.data[i * 4 + 2] = base[2] + k * 0.6 + j;
    img.data[i * 4 + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(reps, reps); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}
const ground = new THREE.Mesh(new THREE.CircleGeometry(40000, 128),
  new THREE.MeshStandardMaterial({ map: noiseTexture([86, 124, 58], 46, 256, 420), roughness: 1, metalness: 0 }));
ground.rotation.x = -Math.PI / 2; ground.position.y = -60;
ground.receiveShadow = true;
scene.add(ground);
const slab = new THREE.Mesh(new THREE.BoxGeometry(1900, 60, 1900),
  new THREE.MeshStandardMaterial({ map: noiseTexture([168, 168, 162], 22, 256, 3), roughness: 0.92 }));
slab.position.y = -30; slab.receiveShadow = true;
scene.add(slab);

// ------------------------------------------------------------------ materials (physically based)
const std = (o) => new THREE.MeshStandardMaterial(o);
const M = {
  alu: std({ color: 0xc4c8cd, metalness: 0.92, roughness: 0.3 }),
  panel: std({ color: 0xefefeb, metalness: 0.12, roughness: 0.42 }),
  deck: std({ color: 0xf4f4f1, metalness: 0.04, roughness: 0.72 }),
  rail: std({ color: 0x9da3a9, metalness: 1.0, roughness: 0.22 }),
  steel: std({ color: 0xbcc0c5, metalness: 1.0, roughness: 0.28 }),
  rubber: std({ color: 0x141414, roughness: 0.9 }),
  motor: std({ color: 0x25272b, metalness: 0.65, roughness: 0.42 }),
  print: std({ color: 0xe8661e, roughness: 0.6 }),
  cover: new THREE.MeshPhysicalMaterial({ color: 0xf3f7fa, metalness: 0, roughness: 0.3, transmission: 0.6, thickness: 6,
                                          ior: 1.58, side: THREE.DoubleSide }),
  copper: std({ color: 0xc47a46, metalness: 1.0, roughness: 0.26, emissive: 0xff5a00, emissiveIntensity: 0 }),
  pacf: std({ color: 0x2b2d32, metalness: 0.05, roughness: 0.74 }),
  anod: std({ color: 0xb3261e, metalness: 0.85, roughness: 0.33 }),
  nylon: std({ color: 0xf1efe6, roughness: 0.6 }),
  tpu: std({ color: 0xf2b705, roughness: 0.7 }),
  pcbG: std({ color: 0x1d6b3a, metalness: 0.25, roughness: 0.5 }),
  pcbB: std({ color: 0x1a1c21, metalness: 0.25, roughness: 0.5 }),
  batt: std({ color: 0xe0b21c, metalness: 0.15, roughness: 0.5 }),
  bell: std({ color: 0x40444c, metalness: 0.9, roughness: 0.28 }),
  gps: std({ color: 0xf6f6f6, roughness: 0.38 }),
  black: std({ color: 0x0e0e10, roughness: 0.55 }),
  prop: std({ color: 0x15161a, roughness: 0.42, transparent: true }),
};
function pick(n) {
  if (!n) return null;
  if (/^dockCOVER_[RL]$/.test(n)) return M.cover;
  if (n.startsWith("dockCOVER_")) return M.print;
  if (n === "dock_frame") return M.alu;
  if (n === "dock_panels") return M.panel;
  if (n === "dock_deck") return M.deck;
  if (n === "dockREF_marker") return M.black;
  if (n.startsWith("dockREF_contact_pad")) return M.copper;
  if (n.startsWith("dockREF_rail")) return M.rail;
  if (n.startsWith("dockBELT")) return M.rubber;
  if (n.startsWith("dockREF_nema") || n.startsWith("dockREF_cover_motor")) return M.motor;
  if (/^dockREF_(pulley|idler|carriage)/.test(n) || n.startsWith("dock_shaft")) return M.steel;
  if (n.startsWith("dock_bar_bracket")) return M.print;
  if (/^dock_bar_[xy]/.test(n)) return M.alu;
  if (n.startsWith("dock_")) return M.print;
  if (/^(bottom_plate|arm_|mid_plate|top_plate|camera_plate|battery_tray|gps_plate|landing_leg|foot_|charge_case)/.test(n)) return M.pacf;
  if (/^standoff_(\d|rear|tray)/.test(n)) return M.anod;
  if (/^standoff_(rpi|gps)/.test(n)) return M.nylon;
  if (n === "antenna_mount") return M.tpu;
  if (n.startsWith("REF_motor")) return M.bell;
  if (n.startsWith("REF_contact")) return M.steel;
  if (n === "REF_battery") return M.batt;
  if (/^REF_(bms|rpi|down_cam|bec)/.test(n)) return M.pcbG;
  if (/^REF_(esc|fc|elrs_rx|vtx|charge_bridge|telemetry)/.test(n)) return M.pcbB;
  if (n === "REF_gps") return M.gps;
  if (n.startsWith("REF_ant") || n === "REF_fpv_cam") return M.black;
  if (n === "prop_blades") return M.prop;
  return null;
}
function prepare(root) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    let p = o.parent, mat = null;                 // part = the group above the per-face meshes
    while (p && !(mat = pick(p.name))) p = p.parent;
    if (!mat) mat = pick(o.name);
    if (mat) o.material = mat;
    else if (o.material) { o.material.roughness = 0.6; o.material.metalness = 0.1; }
    o.castShadow = o.material !== M.cover;
    o.receiveShadow = true;
  });
  return root;
}

// ------------------------------------------------------------------ models
const loader = new GLTFLoader();
const load = (f) => new Promise((res, rej) => loader.load(`models/${f}.glb`, (g) => res(prepare(g.scene)), undefined, rej));
const [dock, covR, covL, pxp, pxn, pyp, pyn, drone, prop] = await Promise.all(
  ["dock_body", "cover_R", "cover_L", "pusher_xp", "pusher_xn", "pusher_yp", "pusher_yn", "drone", "prop"].map(load));
document.getElementById("load").remove();

const world = new THREE.Group();
scene.add(world);
const dockGroup = new THREE.Group();
world.add(dockGroup);
dockGroup.add(dock);
const pivotR = new THREE.Group(), pivotL = new THREE.Group();
pivotR.position.set(XH, ZH, 0); covR.position.set(-XH, -ZH, 0); pivotR.add(covR);
pivotL.position.set(-XH, ZH, 0); covL.position.set(XH, -ZH, 0); pivotL.add(covL);
dockGroup.add(pivotR, pivotL, pxp, pxn, pyp, pyn);

// printed ArUco-style landing marker on the deck
{
  const c = document.createElement("canvas"); c.width = c.height = 600;
  const g = c.getContext("2d");
  g.fillStyle = "#fff"; g.fillRect(0, 0, 600, 600);
  g.fillStyle = "#000"; g.fillRect(25, 25, 550, 550);
  const bits = [[1, 0, 1, 1], [0, 1, 0, 1], [0, 0, 1, 1], [1, 0, 0, 0]];
  bits.forEach((row, i) => row.forEach((b, j) => { if (b) { g.fillStyle = "#fff"; g.fillRect(117 + j * 91.5, 117 + i * 91.5, 91.5, 91.5); } }));
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(129.5, 129.5), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.8 }));
  m.rotation.x = -Math.PI / 2; m.position.y = ZDECK + 0.15; m.receiveShadow = true;
  dockGroup.add(m);
}

// drone rig + spinning props with a motion-blur disc
const rig = new THREE.Group();
world.add(rig);
rig.add(drone);
const props = [];
const SPIN = [-1, 1, -1, 1];
cfg.motors_xy.forEach(([mx, my], i) => {
  const h = new THREE.Group();
  h.position.set(mx, cfg.prop_z, -my);
  const p = prop.clone(true);
  h.add(p);
  const disc = new THREE.Mesh(new THREE.CircleGeometry(88.9, 72),
    new THREE.MeshBasicMaterial({ color: 0x2a2c31, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
  disc.rotation.x = -Math.PI / 2; disc.position.y = 1.5;
  h.add(disc);
  rig.add(h);
  props.push({ blades: p, disc, dir: SPIN[i] });
});

// ------------------------------------------------------------------ the cycle
const STEPS = [
  [0, "Docked: covers closed, drone centred and charging through its feet"],
  [3, "Mission request: charging stops"],
  [4.5, "Covers flip 180° open on their worm-gear motors"],
  [10.5, "Pushers park at the edges: the deck is clear"],
  [13, "Motors spin up"],
  [14.5, "Take-off straight up: nothing around the props"],
  [18.5, "Flying the mission"],
  [26.5, "Return home: precision landing on the ArUco marker"],
  [31.5, "Touch-down, motors stop"],
  [32.5, "X pushers slide the legs to the centre and square the yaw"],
  [35.5, "Y pushers finish centring: the feet sit on the copper pads"],
  [38.5, "Covers close over the drone"],
  [44.5, "Charging: 25.2 V CC/CV through the four foot contacts"],
];
const END = 48.5;
const clamp01 = (x) => Math.min(1, Math.max(0, x));
const ease = (x) => { x = clamp01(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const seg = (t, a, b) => ease((t - a) / (b - a));
const lin = (t, a, b) => clamp01((t - a) / (b - a));
const mix = (a, b, u) => a + (b - a) * u;
const OX = 90, OY = -60, OYAW = 14;          // where the drone touches down (mm, deg): off-centre and turned

function flight(t) {                          // drone position above the deck centre (CAD mm) and yaw (deg)
  if (t < 14.5) return [0, 0, 0, 0];
  if (t < 18.5) return [0, 0, 1500 * seg(t, 14.5, 18.5), 0];
  if (t < 20.5) { const u = seg(t, 18.5, 20.5); return [2200 * u, 0, mix(1500, 1900, u), 90 * u]; }
  if (t < 24.5) { const a = 2 * Math.PI * lin(t, 20.5, 24.5); return [2200 * Math.cos(a), 2200 * Math.sin(a), 1900, 90 + a * 180 / Math.PI]; }
  if (t < 26.5) { const u = seg(t, 24.5, 26.5); return [mix(2200, OX, u), mix(0, OY, u), mix(1900, 900, u), mix(450, 360 + OYAW, u)]; }
  if (t < 31.5) { const u = lin(t, 26.5, 31.5); return [OX, OY, 900 * Math.pow(1 - u, 3), 360 + OYAW]; }
  return [OX, OY, 0, 360 + OYAW];
}
function stateAt(t) {
  const s = {};
  s.cover = t < 4.5 ? 0 : t < 10.5 ? 180 * seg(t, 4.5, 10.5) : t < 38.5 ? 180 : t < 44.5 ? 180 * (1 - seg(t, 38.5, 44.5)) : 0;
  if (t < 10.5) { s.bx = XC; s.by = YC; }
  else if (t < 13) { const u = seg(t, 10.5, 13); s.bx = mix(XC, PARK, u); s.by = mix(YC, PARK, u); }
  else if (t < 32.5) { s.bx = PARK; s.by = PARK; }
  else if (t < 35.5) { s.bx = mix(PARK, XC, seg(t, 32.5, 35.5)); s.by = PARK; }
  else if (t < 38.5) { s.bx = XC; s.by = mix(PARK, YC, seg(t, 35.5, 38.5)); }
  else { s.bx = XC; s.by = YC; }
  s.prop = t < 13 ? 0 : t < 14.5 ? lin(t, 13, 14.5) : t < 31.5 ? 1 : t < 32.5 ? 1 - lin(t, 31.5, 32.5) : 0;
  let [x, y, z, yaw] = flight(t);
  if (t >= 32.5 && t < 44.5 + 99) {           // the pushers move the drone once they reach its legs
    const dx = Math.min(OX, Math.max(0, s.bx - XC));
    const dy = t < 35.5 ? OY : -Math.min(-OY, Math.max(0, s.by - YC));
    x = dx; y = dy; yaw = 360 + OYAW * (dx / OX);
  }
  if (t < 14.5) { x = 0; y = 0; yaw = 0; }
  s.p = [x, y, z]; s.yaw = yaw;
  s.charge = t < 3 ? 1 : t < 4.5 ? 1 - lin(t, 3, 4.5) : t < 44.5 ? 0 : lin(t, 44.5, 45.5);
  s.step = STEPS.reduce((k, st, i) => (t >= st[0] ? i : k), 0);
  return s;
}

const up = new THREE.Vector3(0, 1, 0);
function apply(t, clock = 0, studio = false) {
  const s = stateAt(t);
  pivotR.rotation.z = -THREE.MathUtils.degToRad(s.cover);
  pivotL.rotation.z = THREE.MathUtils.degToRad(s.cover);
  pxp.position.x = s.bx; pxn.position.x = -s.bx;
  pyp.position.z = -s.by; pyn.position.z = s.by;
  const [x, y, z] = s.p;
  rig.position.set(x, (studio ? ZDRONE - ZDECK : ZDRONE) + z, -y);
  // lean into the direction of travel
  const a = stateAt(Math.max(0, t - 0.06)).p, b = stateAt(t + 0.06).p;
  const vx = (b[0] - a[0]) / 0.12, vz = -(b[1] - a[1]) / 0.12;
  const sp = Math.hypot(vx, vz), tilt = z > 5 ? Math.min(0.42, sp / 9000) : 0;
  const qYaw = new THREE.Quaternion().setFromAxisAngle(up, THREE.MathUtils.degToRad(s.yaw));
  const qTilt = sp > 1 ? new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(vz / sp, 0, -vx / sp), tilt) : new THREE.Quaternion();
  rig.quaternion.copy(qTilt.multiply(qYaw));
  props.forEach((p) => {
    p.blades.rotation.y += p.dir * s.prop * 0.55;
    p.disc.material.opacity = 0.26 * s.prop;
  });
  M.prop.opacity = 1 - 0.75 * s.prop;
  M.copper.emissiveIntensity = s.charge * (0.55 + 0.35 * Math.sin(clock * 4));
  return s;
}

// ------------------------------------------------------------------ cinematic camera
function cineCamera(t, s, k = 0.06) {
  const z = s.p[2], w = clamp01(z / 700);                       // how much the camera follows the drone
  const dock = new THREE.Vector3(0, 420, 0), dr = rig.position;
  const tg = dock.clone().lerp(dr, 0.72 * w);
  const horiz = Math.hypot(dr.x, dr.z);
  const r = 2350 + w * (1.05 * horiz + 0.75 * z);
  const phi = 0.8 + 0.035 * t;
  const goal = new THREE.Vector3(tg.x + r * Math.cos(phi), tg.y + 720 + 0.18 * z, tg.z + r * Math.sin(phi));
  camera.position.lerp(goal, k);
  controls.target.lerp(tg, k * 1.6);
}

// ------------------------------------------------------------------ UI
const $ = (id) => document.getElementById(id);
const stepsEl = $("steps");
STEPS.forEach(([ts, txt], i) => {
  const li = document.createElement("li");
  li.textContent = `${ts.toFixed(1).padStart(4, " ")} s  ${txt}`;
  li.onclick = () => { T = ts + 0.01; };
  stepsEl.appendChild(li);
});
let T = 0, playing = true, speed = 1, cine = true, studio = false, recording = false;
const speeds = [0.5, 1, 2];
$("play").onclick = () => { playing = !playing; $("play").textContent = playing ? "❚❚ Pause" : "▶ Play"; $("play").classList.toggle("on", playing); };
$("restart").onclick = () => { T = 0; };
$("speed").onclick = () => { speed = speeds[(speeds.indexOf(speed) + 1) % speeds.length]; $("speed").textContent = `${speed}×`; };
$("prog").onclick = (e) => { const r = e.currentTarget.getBoundingClientRect(); T = END * (e.clientX - r.left) / r.width; };
$("cine").onclick = () => { cine = !cine; $("cine").classList.toggle("on", cine); };
controls.addEventListener("start", () => { if (cine && !recording) { cine = false; $("cine").classList.remove("on"); } });
$("xray").onclick = () => {
  const on = $("xray").classList.toggle("on");
  M.cover.transmission = on ? 0 : 0.6; M.cover.transparent = on; M.cover.opacity = on ? 0.18 : 1; M.cover.needsUpdate = true;
};
$("studio").onclick = () => {
  studio = $("studio").classList.toggle("on");
  dockGroup.visible = !studio;
  if (studio) { T = 0; playing = false; cine = false; $("cine").classList.remove("on");
    camera.position.set(620, 420, 700); controls.target.set(0, 60, 0); }
};
function flash(t) { const m = $("msg"); m.textContent = t; m.style.display = "block"; clearTimeout(flash.h); flash.h = setTimeout(() => (m.style.display = "none"), 3500); }

async function saveBlob(blob, name) {
  try {
    const r = await fetch(`save?name=${encodeURIComponent(name)}`, { method: "POST", body: blob });
    if (!r.ok) throw new Error(await r.text());
    flash(`Saved output/viewer/media/${name}`);
  } catch (e) {                                   // no local server: download in the browser instead
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click();
    flash(`Downloaded ${name}`);
  }
}
function renderAt(w, h) {
  renderer.setPixelRatio(1); renderer.setSize(w, h, false);
  camera.aspect = w / h; camera.updateProjectionMatrix();
}
function restoreSize() {
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
}
async function capture(name, t = T, cam = null, w = 1920, h = 1080, opts = {}) {
  capturing = true;
  const prevStudio = studio;
  if (opts.studio !== undefined) { studio = opts.studio; dockGroup.visible = !studio; }
  renderAt(w, h);
  if (cam) { camera.position.set(...cam.pos); controls.target.set(...cam.target); }
  for (let i = 0; i < 6; i++) { apply(t, i * 0.1, studio); controls.update(); renderer.render(scene, camera); }
  const blob = await new Promise((r) => renderer.domElement.toBlob(r, "image/png"));
  await saveBlob(blob, name);
  studio = prevStudio; dockGroup.visible = !studio;
  restoreSize();
  capturing = false;
}
$("shot").onclick = () => capture(`docker_drone_${T.toFixed(1).replace(".", "_")}s.png`);

async function record(name = "docker_drone_cycle", w = 1280, h = 720, fps = 30) {
  if (recording) return;
  recording = true; cine = true; $("cine").classList.add("on"); studio = false; dockGroup.visible = true;
  renderAt(w, h);
  const types = ["video/mp4;codecs=avc1.640028", "video/mp4", "video/webm;codecs=vp9", "video/webm"];
  const type = types.find((x) => window.MediaRecorder && MediaRecorder.isTypeSupported(x));
  const stream = renderer.domElement.captureStream(fps);
  const rec = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 8_000_000 });
  const chunks = [];
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const done = new Promise((r) => (rec.onstop = r));
  $("rec").textContent = "● Recording…"; $("rec").classList.add("on");
  T = 0; playing = true; speed = 1; $("speed").textContent = "1×";
  camera.position.set(2350 * Math.cos(0.8), 1150, 2350 * Math.sin(0.8));
  rec.start(500);
  await new Promise((r) => { const iv = setInterval(() => { if (T >= END - 0.05) { clearInterval(iv); r(); } }, 100); });
  rec.stop(); await done;
  const ext = type.includes("mp4") ? "mp4" : "webm";
  await saveBlob(new Blob(chunks, { type }), `${name}.${ext}`);
  $("rec").textContent = "● Record video"; $("rec").classList.remove("on");
  recording = false; restoreSize();
}
$("rec").onclick = () => record();

// frame-by-frame video render: every frame is rendered at a fixed time step (smooth even if the page is in the
// background) and encoded to H.264 MP4 in the browser (WebCodecs + mp4-muxer); saved by serve.py
async function renderVideo(fps = 30, w = 1280, h = 720, t0 = 0, t1 = END, name = "docker_drone_cycle.mp4") {
  recording = true; capturing = true; studio = false; dockGroup.visible = true; playing = false;
  renderAt(w, h);
  const { Muxer, ArrayBufferTarget } = await import("https://cdn.jsdelivr.net/npm/mp4-muxer@5.1.3/build/mp4-muxer.mjs");
  const muxer = new Muxer({ target: new ArrayBufferTarget(), video: { codec: "avc", width: w, height: h }, fastStart: "in-memory" });
  const encoder = new VideoEncoder({ output: (chunk, meta) => muxer.addVideoChunk(chunk, meta), error: (e) => console.error(e) });
  encoder.configure({ codec: "avc1.640028", width: w, height: h, bitrate: 7_000_000, framerate: fps });
  const n = Math.round((t1 - t0) * fps), dt = 1 / fps;
  let s = apply(t0, t0);
  cineCamera(t0, s, 1);                                          // start already framed
  const comp = document.createElement("canvas"); comp.width = w; comp.height = h;
  const g = comp.getContext("2d");
  const rr = (x, y, ww, hh, r) => { g.beginPath(); g.roundRect(x, y, ww, hh, r); g.fill(); };
  for (let i = 0; i <= n; i++) {
    const t = t0 + i * dt;
    s = apply(t, t);
    cineCamera(t, s, 1 - Math.exp(-dt * 3.2));
    controls.update();
    renderer.render(scene, camera);
    g.drawImage(renderer.domElement, 0, 0);                    // burn the caption + progress into the frame
    const step = STEPS[s.step], k = s.step + 1;
    g.font = "600 26px Segoe UI, system-ui, sans-serif";
    const tw = g.measureText(step[1]).width;
    g.fillStyle = "rgba(14,18,26,0.74)"; rr(28, h - 118, Math.max(420, tw + 48), 86, 14);
    g.fillStyle = "#ff7a1a"; g.font = "700 17px Segoe UI, system-ui, sans-serif";
    g.fillText(`DOCKER DRONE  ·  STEP ${k} / ${STEPS.length}`, 52, h - 84);
    g.fillStyle = "#f1f4f8"; g.font = "600 26px Segoe UI, system-ui, sans-serif";
    g.fillText(step[1], 52, h - 50);
    g.fillStyle = "rgba(255,255,255,0.25)"; g.fillRect(0, h - 6, w, 6);
    g.fillStyle = "#ff7a1a"; g.fillRect(0, h - 6, (w * t) / END, 6);
    const vf = new VideoFrame(comp, { timestamp: Math.round((i * 1e6) / fps), duration: Math.round(1e6 / fps) });
    encoder.encode(vf, { keyFrame: i % (2 * fps) === 0 });
    vf.close();
    if (i % 30 === 0) { await encoder.flush(); $("time").textContent = `rendering ${i}/${n}`; }
  }
  await encoder.flush();
  muxer.finalize();
  await saveBlob(new Blob([muxer.target.buffer], { type: "video/mp4" }), name);
  recording = false; capturing = false; restoreSize(); playing = true;
  return { frames: n + 1, bytes: muxer.target.buffer.byteLength };
}

// automation hooks (used to save the product pictures)
window.DOCK = { capture, record, renderVideo, setTime: (t) => (T = t), pause: () => { playing = false; },
                play: () => { playing = true; }, stateAt, END, camera, controls, rig, STEPS };

// ------------------------------------------------------------------ loop
let last = performance.now(), clock = 0, sizeW = 0, sizeH = 0, capturing = false;
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now; clock += dt;
  if (!recording && !capturing && innerWidth && innerHeight && (innerWidth !== sizeW || innerHeight !== sizeH)) {
    sizeW = innerWidth; sizeH = innerHeight; restoreSize();        // the pane may start at 0 x 0
  }
  if (playing) { T += dt * speed; if (T >= END) T = recording ? END : 0; }
  const s = apply(T, clock, studio);
  if (cine && !studio) cineCamera(T, s, 1 - Math.exp(-dt * 3.2));
  controls.update();
  renderer.render(scene, camera);
  $("cap").textContent = studio ? "The printed PA-CF drone: 7-inch props, Pi 5 on top, contact feet" : STEPS[s.step][1];
  [...stepsEl.children].forEach((li, i) => li.classList.toggle("on", i === s.step));
  $("prog").firstElementChild.style.width = `${(100 * T) / END}%`;
  $("time").textContent = `${T.toFixed(1)} / ${END} s`;
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
addEventListener("resize", () => { if (!recording) restoreSize(); });
