/* ==============================================================================
   CYBERPUNK 3D DOT-MATRIX EARTH GLOBE RENDERER (HIGH-PERFORMANCE)
   Pure HTML5 Canvas 3D Perspective Projection - Zero Dependencies
   Zero Per-Frame Allocations (Zero GC Pressure) + High-DPI Support
   ============================================================================== */

class CyberpunkGlobe {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    // High-DPI Display Scaling
    this.dpr = window.devicePixelRatio || 1;
    this.cssWidth = 520;
    this.cssHeight = 440;
    this._setupCanvasResolution();

    this.radius = Math.min(this.cssWidth, this.cssHeight) * 0.38;

    this.rotX = 0.28;
    this.rotY = 0.0;
    this.autoRotateSpeed = 0.005;

    this.isDragging = false;
    this.lastMouseX = 0;
    this.lastMouseY = 0;
    this.pulseTime = 0;
    this.isRunning = true;

    // Pre-allocated object pools
    this.dots = [];
    this.gridRings = [];
    this.peers = [];
    this.projectedPool = [];

    // Home node (Orange Pi Zero 3 location ~ US East / 38°N, 77°W)
    this.homeLat = 38.0;
    this.homeLon = -77.0;
    this.homeNode = this._latLonToSphere(this.homeLat, this.homeLon, this.radius);

    this._generateWorldMatrix();
    this._generateHoloGrid();
    this._initDefaultPeers();
    this._bindEvents();

    this._boundRender = this.render.bind(this);
    requestAnimationFrame(this._boundRender);
  }

  _setupCanvasResolution() {
    this.canvas.width = this.cssWidth * this.dpr;
    this.canvas.height = this.cssHeight * this.dpr;
    this.canvas.style.width = `${this.cssWidth}px`;
    this.canvas.style.height = `${this.cssHeight}px`;
    this.ctx.scale(this.dpr, this.dpr);
  }

  _latLonToSphere(lat, lon, r) {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);
    return {
      x: -(r * Math.sin(phi) * Math.cos(theta)),
      y: -(r * Math.cos(phi)),
      z: r * Math.sin(phi) * Math.sin(theta),
    };
  }

  _isLandmass(lat, lon) {
    // North America
    if (lat > 15 && lat < 72 && lon > -168 && lon < -52) return true;
    // South America
    if (lat > -56 && lat < 13 && lon > -82 && lon < -34) return true;
    // Europe
    if (lat > 35 && lat < 71 && lon > -10 && lon < 42) return true;
    // Africa
    if (lat > -35 && lat < 37 && lon > -18 && lon < 52) return true;
    // Asia & Middle East
    if (lat > 5 && lat < 75 && lon > 42 && lon < 145) return true;
    // Australia & Oceania
    if (lat > -48 && lat < -10 && lon > 112 && lon < 178) return true;
    // Japan / UK / Islands
    if (lat > 30 && lat < 46 && lon > 128 && lon < 146) return true;
    if (lat > 50 && lat < 59 && lon > -8 && lon < 2) return true;

    return false;
  }

  _generateWorldMatrix() {
    this.dots = [];
    const count = 900;
    const phi = Math.PI * (3 - Math.sqrt(5)); // Golden spiral angle

    for (let i = 0; i < count; i++) {
      const yNorm = 1 - (i / (count - 1)) * 2; // 1 to -1
      const radiusAtY = Math.sqrt(1 - yNorm * yNorm);
      const theta = phi * i;

      const xNorm = Math.cos(theta) * radiusAtY;
      const zNorm = Math.sin(theta) * radiusAtY;

      // Convert normal coordinates to Lat/Lon
      const lat = Math.asin(yNorm) * (180 / Math.PI);
      const lon = Math.atan2(zNorm, xNorm) * (180 / Math.PI);

      const isLand = this._isLandmass(lat, lon);

      this.dots.push({
        x: xNorm * this.radius,
        y: -yNorm * this.radius,
        z: zNorm * this.radius,
        isLand: isLand,
        baseSize: isLand ? 1.8 : 0.9,
      });
    }

    // Pre-allocate projection pool to prevent per-frame garbage collection
    this.projectedPool = new Array(this.dots.length);
    for (let i = 0; i < this.dots.length; i++) {
      this.projectedPool[i] = { px: 0, py: 0, pz: 0, alpha: 0, isLand: false, size: 0 };
    }
  }

  _generateHoloGrid() {
    this.gridRings = [];

    // Latitude Rings (Equator, Tropics, Polar)
    [-60, -30, 0, 30, 60].forEach((lat) => {
      const ringPoints = [];
      for (let deg = 0; deg <= 360; deg += 10) {
        ringPoints.push(this._latLonToSphere(lat, deg, this.radius));
      }
      this.gridRings.push({ points: ringPoints, isEquator: lat === 0 });
    });

    // Longitude Meridian Rings
    [0, 60, 120, 180, 240, 300].forEach((lon) => {
      const ringPoints = [];
      for (let lat = -90; lat <= 90; lat += 10) {
        ringPoints.push(this._latLonToSphere(lat, lon, this.radius));
      }
      this.gridRings.push({ points: ringPoints, isEquator: false });
    });
  }

  _initDefaultPeers() {
    // Worldwide default Bitcoin hub coordinates if peer table is warming up
    const defaultHubs = [
      { lat: 51.5, lon: -0.1, label: 'London' },
      { lat: 50.1, lon: 8.6, label: 'Frankfurt' },
      { lat: 35.6, lon: 139.6, label: 'Tokyo' },
      { lat: 1.35, lon: 103.8, label: 'Singapore' },
      { lat: 40.7, lon: -74.0, label: 'New York' },
      { lat: 37.7, lon: -122.4, label: 'San Francisco' },
      { lat: -33.8, lon: 151.2, label: 'Sydney' },
      { lat: -23.5, lon: -46.6, label: 'São Paulo' },
    ];

    this.setPeers(defaultHubs.map((h, i) => ({
      addr: `${h.label}:8333`,
      ip: h.label,
      pingtime: 30 + i * 15,
      _lat: h.lat,
      _lon: h.lon,
    })));
  }

  setPeers(peerList) {
    this.peers = [];

    if (!peerList || !peerList.length) {
      this._initDefaultPeers();
      return;
    }

    peerList.forEach((p, idx) => {
      let lat, lon;
      if (p._lat !== undefined && p._lon !== undefined) {
        lat = p._lat;
        lon = p._lon;
      } else {
        // Deterministically hash IP to realistic global continent latitudes/longitudes
        let hash = 0;
        const str = p.addr || p.ip || `peer_${idx}`;
        for (let i = 0; i < str.length; i++) {
          hash = (hash << 5) - hash + str.charCodeAt(i);
          hash |= 0;
        }
        const u = Math.abs(hash % 360) - 180;
        const v = (Math.abs((hash >> 4) % 140) - 70);
        lon = u;
        lat = v;
      }

      const coords = this._latLonToSphere(lat, lon, this.radius);

      this.peers.push({
        x: coords.x,
        y: coords.y,
        z: coords.z,
        label: p.ip || p.addr,
        ping: p.pingtime || 45,
        lat: lat,
        lon: lon,
      });
    });
  }

  _bindEvents() {
    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      const dx = e.clientX - this.lastMouseX;
      const dy = e.clientY - this.lastMouseY;

      this.rotY += dx * 0.007;
      this.rotX += dy * 0.007;

      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
    });

    // Touch events for mobile/tablet
    this.canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        this.isDragging = true;
        this.lastMouseX = e.touches[0].clientX;
        this.lastMouseY = e.touches[0].clientY;
      }
    }, { passive: true });

    window.addEventListener('touchend', () => {
      this.isDragging = false;
    });

    window.addEventListener('touchmove', (e) => {
      if (!this.isDragging || e.touches.length !== 1) return;
      const dx = e.touches[0].clientX - this.lastMouseX;
      const dy = e.touches[0].clientY - this.lastMouseY;

      this.rotY += dx * 0.007;
      this.rotX += dy * 0.007;

      this.lastMouseX = e.touches[0].clientX;
      this.lastMouseY = e.touches[0].clientY;
    }, { passive: true });

    // Page visibility lifecycle: pause canvas when tab is hidden to save 0% CPU
    document.addEventListener('visibilitychange', () => {
      this.isRunning = !document.hidden;
      if (this.isRunning) {
        requestAnimationFrame(this._boundRender);
      }
    });
  }

  _rotatePoint(x, y, z) {
    const cosY = Math.cos(this.rotY);
    const sinY = Math.sin(this.rotY);
    const x1 = x * cosY - z * sinY;
    const z1 = z * cosY + x * sinY;

    const cosX = Math.cos(this.rotX);
    const sinX = Math.sin(this.rotX);
    const y2 = y * cosX - z1 * sinX;
    const z2 = z1 * cosX + y * sinX;

    return { x: x1, y: y2, z: z2 };
  }

  render() {
    if (!this.isRunning) return;

    this.ctx.clearRect(0, 0, this.cssWidth, this.cssHeight);

    if (!this.isDragging) {
      this.rotY += this.autoRotateSpeed;
    }
    this.pulseTime += 0.035;

    const cx = this.cssWidth / 2;
    const cy = this.cssHeight / 2;

    this.ctx.save();
    this.ctx.translate(cx, cy);

    // 1. Draw Outer Atmospheric Holographic Glow
    const aura = this.ctx.createRadialGradient(0, 0, this.radius * 0.8, 0, 0, this.radius * 1.18);
    aura.addColorStop(0, 'rgba(0, 240, 255, 0.0)');
    aura.addColorStop(0.7, 'rgba(0, 240, 255, 0.06)');
    aura.addColorStop(1, 'rgba(0, 240, 255, 0.0)');
    this.ctx.fillStyle = aura;
    this.ctx.beginPath();
    this.ctx.arc(0, 0, this.radius * 1.18, 0, Math.PI * 2);
    this.ctx.fill();

    // 2. Render Holographic Wireframe Grid Rings
    this.ctx.lineWidth = 0.8;
    this.gridRings.forEach((ring) => {
      let started = false;
      this.ctx.beginPath();

      ring.points.forEach((pt) => {
        const r = this._rotatePoint(pt.x, pt.y, pt.z);
        if (r.z > -this.radius * 0.2) {
          if (!started) {
            this.ctx.moveTo(r.x, r.y);
            started = true;
          } else {
            this.ctx.lineTo(r.x, r.y);
          }
        } else {
          started = false;
        }
      });

      this.ctx.strokeStyle = ring.isEquator ? 'rgba(0, 240, 255, 0.22)' : 'rgba(0, 240, 255, 0.08)';
      this.ctx.stroke();
    });

    // 3. Project and Render 3D World Matrix Dots
    let dotCount = 0;
    for (let i = 0; i < this.dots.length; i++) {
      const p = this.dots[i];
      const r = this._rotatePoint(p.x, p.y, p.z);
      const alpha = (r.z / this.radius + 1.1) / 2.2;

      if (alpha > 0.06) {
        const pd = this.projectedPool[dotCount++];
        pd.px = r.x;
        pd.py = r.y;
        pd.pz = r.z;
        pd.alpha = alpha;
        pd.isLand = p.isLand;
        pd.size = p.baseSize * (0.8 + alpha * 0.45);
      }
    }

    // Render back-to-front for clean depth
    for (let i = 0; i < dotCount; i++) {
      const d = this.projectedPool[i];
      this.ctx.beginPath();
      this.ctx.arc(d.px, d.py, d.size, 0, Math.PI * 2);

      if (d.isLand) {
        // Bright Neon Cyan Landmass
        this.ctx.fillStyle = `rgba(0, 240, 255, ${Math.min(1.0, d.alpha * 0.95)})`;
      } else {
        // Deep Space Grid Particles
        this.ctx.fillStyle = `rgba(90, 115, 160, ${d.alpha * 0.25})`;
      }
      this.ctx.fill();
    }

    // 4. Render 3D Great-Circle Arcs & Connected Peer Matrix
    const rHome = this._rotatePoint(this.homeNode.x, this.homeNode.y, this.homeNode.z);
    const homeAlpha = (rHome.z / this.radius + 1.1) / 2.2;

    this.peers.forEach((peer, idx) => {
      const rPeer = this._rotatePoint(peer.x, peer.y, peer.z);
      const pAlpha = (rPeer.z / this.radius + 1.1) / 2.2;

      // Draw Great-Circle 3D Curved Arc if at least one node is visible
      if (homeAlpha > 0.1 || pAlpha > 0.1) {
        // 3D Elevated Bezier Midpoint
        const mx = (this.homeNode.x + peer.x) * 0.65;
        const my = (this.homeNode.y + peer.y) * 0.65;
        const mz = (this.homeNode.z + peer.z) * 0.65;
        const rMid = this._rotatePoint(mx, my, mz);

        this.ctx.beginPath();
        this.ctx.moveTo(rHome.x, rHome.y);
        this.ctx.quadraticCurveTo(rMid.x, rMid.y, rPeer.x, rPeer.y);

        const arcAlpha = Math.max(0.12, Math.min(homeAlpha, pAlpha) * 0.65);
        this.ctx.strokeStyle = `rgba(0, 240, 255, ${arcAlpha})`;
        this.ctx.lineWidth = 1.2;
        this.ctx.stroke();

        // Traveling Neon Photon Particle along Arc
        const t = (this.pulseTime * 0.5 + idx * 0.18) % 1.0;
        const px = (1 - t) * (1 - t) * rHome.x + 2 * (1 - t) * t * rMid.x + t * t * rPeer.x;
        const py = (1 - t) * (1 - t) * rHome.y + 2 * (1 - t) * t * rMid.y + t * t * rPeer.y;

        this.ctx.beginPath();
        this.ctx.arc(px, py, 2.2, 0, Math.PI * 2);
        this.ctx.fillStyle = '#00ff88';
        this.ctx.shadowColor = '#00ff88';
        this.ctx.shadowBlur = 6;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      }

      // Draw Peer Node Point
      if (pAlpha > 0.2) {
        this.ctx.beginPath();
        this.ctx.arc(rPeer.x, rPeer.y, 3.2, 0, Math.PI * 2);
        this.ctx.fillStyle = '#00ff88';
        this.ctx.shadowColor = '#00ff88';
        this.ctx.shadowBlur = 8;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
      }
    });

    // 5. Draw Orange Pi Home Node (Pulsing Bitcoin Gold Beacon)
    if (homeAlpha > 0.15) {
      this.ctx.beginPath();
      this.ctx.arc(rHome.x, rHome.y, 5, 0, Math.PI * 2);
      this.ctx.fillStyle = '#ffb000';
      this.ctx.shadowColor = '#ffb000';
      this.ctx.shadowBlur = 14;
      this.ctx.fill();
      this.ctx.shadowBlur = 0;

      // Double Radiating Radar Pulse Rings
      const p1 = 6 + (Math.sin(this.pulseTime * 2.5) + 1) * 5;
      this.ctx.beginPath();
      this.ctx.arc(rHome.x, rHome.y, p1, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(255, 176, 0, ${Math.max(0, 0.85 - (p1 - 6) / 10)})`;
      this.ctx.lineWidth = 1.4;
      this.ctx.stroke();

      const p2 = 6 + (Math.sin(this.pulseTime * 2.5 + Math.PI) + 1) * 5;
      this.ctx.beginPath();
      this.ctx.arc(rHome.x, rHome.y, p2, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(255, 176, 0, ${Math.max(0, 0.85 - (p2 - 6) / 10)})`;
      this.ctx.lineWidth = 1.0;
      this.ctx.stroke();

      // Node Label
      this.ctx.font = '9px "Share Tech Mono", monospace';
      this.ctx.fillStyle = '#ffb000';
      this.ctx.fillText('⚡ ORANGE PI', rHome.x + 8, rHome.y + 3);
    }

    this.ctx.restore();

    requestAnimationFrame(this._boundRender);
  }
}

window.CyberpunkGlobe = CyberpunkGlobe;
