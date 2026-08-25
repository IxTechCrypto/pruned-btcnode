/* ==============================================================================
   CYBERPUNK 3D DOT-MATRIX EARTH GLOBE RENDERER
   Pure HTML5 Canvas 3D Perspective Projection (Zero External Libraries)
   ============================================================================== */

class CyberpunkGlobe {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.width = this.canvas.width;
    this.height = this.canvas.height;
    this.radius = Math.min(this.width, this.height) * 0.40;

    this.rotX = 0.25;
    this.rotY = 0.0;
    this.autoRotateSpeed = 0.004;

    this.isDragging = false;
    this.lastMouseX = 0;
    this.lastMouseY = 0;

    this.dots = [];
    this.peers = [];
    this.arcs = [];
    this.pulseTime = 0;

    this._generateSpherePoints();
    this._bindEvents();
    this.render();
  }

  _generateSpherePoints() {
    // Generate Fibonacci spiral dot matrix for uniform sphere coverage
    const count = 720;
    const phi = Math.PI * (3 - Math.sqrt(5)); // Golden ratio angle

    for (let i = 0; i < count; i++) {
      const y = 1 - (i / (count - 1)) * 2; // -1 to 1
      const radiusAtY = Math.sqrt(1 - y * y);
      const theta = phi * i;

      const x = Math.cos(theta) * radiusAtY;
      const z = Math.sin(theta) * radiusAtY;

      // Classify some dots as landmass/major hubs for visual texture
      const isLand = (Math.sin(x * 3) + Math.cos(y * 4) + Math.sin(z * 3)) > 0.3;

      this.dots.push({
        x: x * this.radius,
        y: y * this.radius,
        z: z * this.radius,
        isLand: isLand,
        baseSize: isLand ? 1.6 : 1.0,
      });
    }
  }

  setPeers(peerList) {
    this.peers = [];
    this.arcs = [];

    // Our home node (e.g. Lat ~37, Long ~-122 or similar visual coordinate)
    const homeNode = {
      x: this.radius * 0.6,
      y: this.radius * -0.4,
      z: this.radius * 0.69,
      isHome: true,
    };

    peerList.forEach((p, idx) => {
      // Deterministically map IP string to sphere coordinates
      let hash = 0;
      for (let i = 0; i < p.addr.length; i++) {
        hash = (hash << 5) - hash + p.addr.charCodeAt(i);
        hash |= 0;
      }

      const u = Math.abs(hash % 1000) / 1000;
      const v = Math.abs((hash >> 3) % 1000) / 1000;
      const theta = u * 2 * Math.PI;
      const phi = Math.acos(2 * v - 1);

      const px = this.radius * Math.sin(phi) * Math.cos(theta);
      const py = this.radius * Math.cos(phi);
      const pz = this.radius * Math.sin(phi) * Math.sin(theta);

      const peerNode = {
        x: px,
        y: py,
        z: pz,
        ip: p.ip || p.addr,
        ping: p.pingtime || 50,
      };

      this.peers.push(peerNode);
      this.arcs.push({
        from: homeNode,
        to: peerNode,
        progress: (idx * 0.15) % 1.0,
      });
    });

    this.homeNode = homeNode;
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

      this.rotY += dx * 0.008;
      this.rotX += dy * 0.008;

      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
    });

    // Touch support for mobile
    this.canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        this.isDragging = true;
        this.lastMouseX = e.touches[0].clientX;
        this.lastMouseY = e.touches[0].clientY;
      }
    });

    window.addEventListener('touchend', () => {
      this.isDragging = false;
    });

    window.addEventListener('touchmove', (e) => {
      if (!this.isDragging || e.touches.length !== 1) return;
      const dx = e.touches[0].clientX - this.lastMouseX;
      const dy = e.touches[0].clientY - this.lastMouseY;

      this.rotY += dx * 0.008;
      this.rotX += dy * 0.008;

      this.lastMouseX = e.touches[0].clientX;
      this.lastMouseY = e.touches[0].clientY;
    });
  }

  _rotatePoint(x, y, z) {
    // Rotate Y
    const cosY = Math.cos(this.rotY);
    const sinY = Math.sin(this.rotY);
    const x1 = x * cosY - z * sinY;
    const z1 = z * cosY + x * sinY;

    // Rotate X
    const cosX = Math.cos(this.rotX);
    const sinX = Math.sin(this.rotX);
    const y2 = y * cosX - z1 * sinX;
    const z2 = z1 * cosX + y * sinX;

    return { x: x1, y: y2, z: z2 };
  }

  render() {
    this.ctx.clearRect(0, 0, this.width, this.height);

    if (!this.isDragging) {
      this.rotY += this.autoRotateSpeed;
    }
    this.pulseTime += 0.03;

    const cx = this.width / 2;
    const cy = this.height / 2;

    // 1. Draw Outer Glowing Ring & Latitudes
    this.ctx.save();
    this.ctx.translate(cx, cy);

    // Subtle atmospheric aura
    const gradient = this.ctx.createRadialGradient(0, 0, this.radius * 0.85, 0, 0, this.radius * 1.15);
    gradient.addColorStop(0, 'rgba(0, 240, 255, 0.0)');
    gradient.addColorStop(0.5, 'rgba(0, 240, 255, 0.05)');
    gradient.addColorStop(1, 'rgba(0, 240, 255, 0.0)');
    this.ctx.fillStyle = gradient;
    this.ctx.beginPath();
    this.ctx.arc(0, 0, this.radius * 1.15, 0, Math.PI * 2);
    this.ctx.fill();

    // Equatorial Ring
    this.ctx.strokeStyle = 'rgba(0, 240, 255, 0.15)';
    this.ctx.lineWidth = 1;
    this.ctx.beginPath();
    this.ctx.ellipse(0, 0, this.radius, this.radius * Math.sin(this.rotX), 0, 0, Math.PI * 2);
    this.ctx.stroke();

    // 2. Project and Sort All 3D Matrix Dots
    const projectedDots = [];

    for (let i = 0; i < this.dots.length; i++) {
      const p = this.dots[i];
      const r = this._rotatePoint(p.x, p.y, p.z);

      // Depth alpha (front is bright, back is dimmed)
      const alpha = (r.z / this.radius + 1.1) / 2.2;
      if (alpha > 0.05) {
        projectedDots.push({
          px: r.x,
          py: r.y,
          pz: r.z,
          alpha: alpha,
          isLand: p.isLand,
          size: p.baseSize * (0.8 + alpha * 0.5),
        });
      }
    }

    // Sort by Z depth
    projectedDots.sort((a, b) => a.pz - b.pz);

    // 3. Draw Projected Matrix Dots
    for (let i = 0; i < projectedDots.length; i++) {
      const d = projectedDots[i];
      this.ctx.beginPath();
      this.ctx.arc(d.px, d.py, d.size, 0, Math.PI * 2);

      if (d.isLand) {
        this.ctx.fillStyle = `rgba(0, 240, 255, ${d.alpha * 0.85})`;
      } else {
        this.ctx.fillStyle = `rgba(120, 140, 180, ${d.alpha * 0.3})`;
      }
      this.ctx.fill();
    }

    // 4. Render Active Peer Nodes and Arcs
    if (this.homeNode) {
      const rHome = this._rotatePoint(this.homeNode.x, this.homeNode.y, this.homeNode.z);
      const homeAlpha = (rHome.z / this.radius + 1.1) / 2.2;

      // Draw Home Node (Bitcoin Orange Beacon)
      if (homeAlpha > 0.2) {
        this.ctx.beginPath();
        this.ctx.arc(rHome.px, rHome.py, 4.5, 0, Math.PI * 2);
        this.ctx.fillStyle = '#ffb000';
        this.ctx.shadowColor = '#ffb000';
        this.ctx.shadowBlur = 12;
        this.ctx.fill();
        this.ctx.shadowBlur = 0;

        // Radiating pulse ring
        const pulseR = 5 + (Math.sin(this.pulseTime * 2) + 1) * 4;
        this.ctx.beginPath();
        this.ctx.arc(rHome.px, rHome.py, pulseR, 0, Math.PI * 2);
        this.ctx.strokeStyle = `rgba(255, 176, 0, ${0.8 - (pulseR - 5) / 8})`;
        this.ctx.lineWidth = 1.2;
        this.ctx.stroke();
      }

      // Draw Peer Nodes & Connection Arcs
      this.peers.forEach((peer, idx) => {
        const rPeer = this._rotatePoint(peer.x, peer.y, peer.z);
        const pAlpha = (rPeer.z / this.radius + 1.1) / 2.2;

        if (pAlpha > 0.2) {
          this.ctx.beginPath();
          this.ctx.arc(rPeer.px, rPeer.py, 3, 0, Math.PI * 2);
          this.ctx.fillStyle = '#00ff88';
          this.ctx.shadowColor = '#00ff88';
          this.ctx.shadowBlur = 8;
          this.ctx.fill();
          this.ctx.shadowBlur = 0;
        }

        // Draw Arc between Home and Peer if both somewhat in front
        if (homeAlpha > 0.1 || pAlpha > 0.1) {
          this.ctx.beginPath();
          this.ctx.moveTo(rHome.px, rHome.py);

          // Bezier control point arched outwards
          const midX = (rHome.px + rPeer.px) / 2 * 1.2;
          const midY = (rHome.py + rPeer.py) / 2 * 1.2;
          this.ctx.quadraticCurveTo(midX, midY, rPeer.px, rPeer.py);

          this.ctx.strokeStyle = `rgba(0, 240, 255, ${Math.min(homeAlpha, pAlpha) * 0.35})`;
          this.ctx.lineWidth = 1;
          this.ctx.stroke();

          // Animated data packet pulse on the arc
          const t = (this.pulseTime * 0.4 + idx * 0.2) % 1.0;
          const px = (1 - t) * (1 - t) * rHome.px + 2 * (1 - t) * t * midX + t * t * rPeer.px;
          const py = (1 - t) * (1 - t) * rHome.py + 2 * (1 - t) * t * midY + t * t * rPeer.py;

          this.ctx.beginPath();
          this.ctx.arc(px, py, 2, 0, Math.PI * 2);
          this.ctx.fillStyle = '#ffffff';
          this.ctx.fill();
        }
      });
    }

    this.ctx.restore();

    requestAnimationFrame(() => this.render());
  }
}

window.CyberpunkGlobe = CyberpunkGlobe;
