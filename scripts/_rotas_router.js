/* Roteamento (Dijkstra) do mapa de rotas - FONTE UNICA.
 * Usado pelo resultados/mapa_rotas.html (navegador, offline) e pela verificacao
 * em Node (scripts/verif_rotas.py roda este mesmo codigo). NAO depende de DOM.
 *
 * Mesma rede e mesmos pesos do script 08_desvios.py / do modelo GAML:
 *   custo (tempo, s) por trecho:
 *     carro -> len / vcarro
 *     moto  -> len / (vcarro * VEL_MODO["moto"]=1.1)
 *     a pe  -> len / VEL_PED (1.3 m/s)   usando so trechos com pedestre permitido
 *   distancia = soma dos comprimentos reais dos trechos do caminho.
 * Desempate deterministico por (custo, no) para casar com o heapq do Python.
 */
(function (root) {
  "use strict";

  // Min-heap binario ordenado por [custo, no] (igual a tupla (custo, no) do heapq).
  function MinHeap() { this.a = []; }
  MinHeap.prototype.size = function () { return this.a.length; };
  MinHeap.prototype._less = function (i, j) {
    var x = this.a[i], y = this.a[j];
    return x[0] < y[0] || (x[0] === y[0] && x[1] < y[1]);
  };
  MinHeap.prototype.push = function (no, custo) {
    var a = this.a; a.push([custo, no]); var i = a.length - 1;
    while (i > 0) { var p = (i - 1) >> 1; if (this._less(i, p)) { var t = a[i]; a[i] = a[p]; a[p] = t; i = p; } else break; }
  };
  MinHeap.prototype.pop = function () {
    var a = this.a, top = a[0], last = a.pop();
    if (a.length) { a[0] = last; var i = 0, n = a.length;
      while (true) { var l = 2 * i + 1, r = l + 1, s = i;
        if (l < n && this._less(l, s)) s = l;
        if (r < n && this._less(r, s)) s = r;
        if (s === i) break; var t = a[i]; a[i] = a[s]; a[s] = t; i = s; } }
    return top; // [custo, no]
  };

  // Calcula a rota do no 'src' ao no 'dst'. 'fechados' e um Set de indices de trecho.
  // modal em {"carro","moto","pe"}. Retorna {ok, nos, edges, dist_m, tempo_s}.
  function rota(DATA, src, dst, modal, fechados) {
    var edges = DATA.edges, N = DATA.nodes.length;
    var velMoto = DATA.vel_moto, velPed = DATA.vel_ped;
    fechados = fechados || new Set();
    // adjacencia: mesma ordem de trechos nos dois lados (determinismo)
    var adj = new Array(N); for (var i = 0; i < N; i++) adj[i] = [];
    for (var e = 0; e < edges.length; e++) {
      if (fechados.has(e)) continue;
      var E = edges[e], u = E[0], v = E[1], len = E[2], vc = E[3], carro = E[4], pe = E[5];
      var ok, w;
      if (modal === "pe") { ok = pe === 1; w = len / velPed; }
      else if (modal === "moto") { ok = carro === 1; w = len / (vc * velMoto); }
      else { ok = carro === 1; w = len / vc; } // carro (padrao)
      if (!ok || !(w > 0)) continue;
      adj[u].push([v, w, e]);
      adj[v].push([u, w, e]);
    }
    var dist = new Float64Array(N); dist.fill(Infinity);
    var prevN = new Int32Array(N); prevN.fill(-1);
    var prevE = new Int32Array(N); prevE.fill(-1);
    dist[src] = 0;
    var heap = new MinHeap(); heap.push(src, 0);
    while (heap.size()) {
      var top = heap.pop(), du = top[0], nu = top[1];
      if (du > dist[nu]) continue;
      if (nu === dst) break;
      var viz = adj[nu];
      for (var k = 0; k < viz.length; k++) {
        var nv = viz[k][0], nd = du + viz[k][1], ed = viz[k][2];
        if (nd < dist[nv]) { dist[nv] = nd; prevN[nv] = nu; prevE[nv] = ed; heap.push(nv, nd); }
      }
    }
    if (!isFinite(dist[dst])) return { ok: false };
    var nos = [], eds = [], x = dst;
    while (x !== -1) { nos.push(x); if (prevE[x] !== -1) eds.push(prevE[x]); x = prevN[x]; }
    nos.reverse(); eds.reverse();
    var distM = 0; for (var j = 0; j < eds.length; j++) distM += edges[eds[j]][2];
    return { ok: true, nos: nos, edges: eds, dist_m: distM, tempo_s: dist[dst] };
  }

  // Conjunto de trechos fechados a partir das interdicoes marcadas + trechos manuais.
  // modoFechamento: "risco" (so trechos <=40 m do risco) ou "inteira" (a via toda).
  function conjuntoFechado(DATA, marcadas, modoFechamento, manuais) {
    var s = new Set();
    for (var m = 0; m < marcadas.length; m++) {
      var it = DATA.interd[marcadas[m]];
      for (var i = 0; i < it.ids.length; i++) {
        var id = it.ids[i];
        if (id < 0 || id >= DATA.edges.length) continue;
        if (modoFechamento === "risco" && DATA.edges[id][7] !== 1) continue;
        s.add(id);
      }
    }
    if (manuais) manuais.forEach(function (id) { s.add(id); });
    return s;
  }

  // No da rede mais proximo de (lat, lon); retorna {no, dist_m} (haversine).
  function noMaisProximo(DATA, lat, lon) {
    var nodes = DATA.nodes, melhor = -1, md = Infinity;
    var R = 6371000, rad = Math.PI / 180, la = lat * rad;
    for (var i = 0; i < nodes.length; i++) {
      var dphi = (nodes[i][0] - lat) * rad, dl = (nodes[i][1] - lon) * rad;
      var a = Math.sin(dphi / 2) * Math.sin(dphi / 2) +
        Math.cos(la) * Math.cos(nodes[i][0] * rad) * Math.sin(dl / 2) * Math.sin(dl / 2);
      var d = 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
      if (d < md) { md = d; melhor = i; }
    }
    return { no: melhor, dist_m: md };
  }

  var API = { rota: rota, conjuntoFechado: conjuntoFechado, noMaisProximo: noMaisProximo, MinHeap: MinHeap };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  root.ROTAS = API;
})(typeof window !== "undefined" ? window : globalThis);
