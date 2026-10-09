/* ============================================================
   OmniAPI —— 双模式数据源适配层
   ------------------------------------------------------------
   ① 优先请求本地 FastAPI 后端（python server.py @ 127.0.0.1:8888）
   ② 请求失败 / 超时（例如 GitHub Pages 纯静态托管，没有后端）
      → 自动降级到本文件内置的演示逻辑，
        保证 6 个 Tab 全部可交互、可演示。

   设计原则：先试真的，真不了才用假的；且当前模式会显示在顶栏，
   不把「演示数据」伪装成「线上数据」。
   ============================================================ */
(function () {
  'use strict';

  var TIMEOUT_MS = 2500;

  function apiCall(path, options) {
    var timeoutMs = (options && options.timeoutMs) || TIMEOUT_MS;
    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, timeoutMs);
    var opts = Object.assign({}, options || {}, { signal: ctrl.signal });
    delete opts.timeoutMs;
    return fetch(path, opts)
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .finally(function () { clearTimeout(timer); });
  }

  /* ---------- 内置演示逻辑：与 server.py 的行为保持一致 ---------- */

  function localGuideChat(userMsg) {
    var msg = (userMsg || '').trim();
    var t0 = performance.now();

    var isCoupon = ['券', '优惠', '打折', '便宜', '省钱', '满减'].some(function (k) { return msg.indexOf(k) >= 0; });
    var isRecommend = ['推荐', '买', '送', '项链', '手串', '戒指', '玉', '翡翠'].some(function (k) { return msg.indexOf(k) >= 0; });
    var isDiff = ['区别', '真假', '莫桑', '培育', '天然', '证书'].some(function (k) { return msg.indexOf(k) >= 0; });

    var steps = [
      { node: '意图识别 (Router)', status: 'done',
        detail: '分类为: ' + (isCoupon ? 'COUPON_QUERY' : (isRecommend ? 'PRODUCT_RECOMMEND' : 'KNOWLEDGE_QA')) },
      { node: '向量库混合检索 (RAG)', status: 'done',
        detail: '检索到 4 条高置信度知识切片，相似度最高 0.942' }
    ];
    var selfCorrected = false;
    var reply;

    if (msg.indexOf('500') >= 0 && msg.indexOf('券') >= 0) {
      selfCorrected = true;
      steps.push({ node: '工具调用 (Tool Calling)', status: 'retry', detail: "调用 get_coupon('500元无门槛') 失败：券面额超出系统上限" });
      steps.push({ node: '⚡ 自动反思与自纠错 (Self-Correction)', status: 'done', detail: '触发纠错策略：自动降级检索最接近规则，回正为【满2000减200】与【新人50元立减】' });
      reply = '非常抱歉呀，小琼帮您查了一下，目前店内没有【500元无门槛券】哦～ 不过小琼为您申请到了当前最划算的组合：\n\n1. **新人专享礼**：满 300 减 50 元立减券；\n2. **珠宝品类大额券**：满 2000 减 200 元满减券！\n\n如果您今天选购【天然和田玉青海老料吊坠】（原价 ¥1,880），再凑单一个小银饰，即可直接立减 200 元，非常划算！需要我帮您锁定领券名额吗？';
    } else if (isRecommend) {
      steps.push({ node: '工具调用 (Tool Calling)', status: 'done', detail: "执行 query_products(category='jade', price_range=[1000, 2500])，命中 3 款商品" });
      steps.push({ node: '决策合成 (Synthesis)', status: 'done', detail: '结合送礼/自戴场景，生成亲和力导购话术' });
      reply = '为您精心挑选了店内两款口碑极高的送礼首选：\n\n🌟 **【琼华·福禄双全】天然和田碧玉平安扣吊坠**\n- 材质：新疆且末老料，油润细腻，附国家级宝玉石质检证书\n- 礼盒：配东方国风锦盒与特调沉香香片\n- 专柜价：¥2,399 ｜ **限时到手价：¥1,680**\n\n💍 **【琼华·月满西楼】天然淡水无瑕珍珠项链**\n- 规格：8-9mm 微瑕近圆，正圆强光皮光极亮\n- **专柜价：¥1,480 ｜ 限时活动价：¥1,120**\n\n两款都非常温润显气质，长辈收到都特别喜欢。您更偏好玉石的内敛还是珍珠的优雅呢？';
    } else if (isDiff) {
      steps.push({ node: '知识检索 (RAG)', status: 'done', detail: '命中珠宝百科知识切片 #381：《莫桑钻与天然钻石光学特质比对》' });
      reply = '这是很多顾客关心的专业问题，小琼为您通俗解答：\n\n1. **物理成分**：天然钻石是纯碳晶体（硬度10）；莫桑石是碳化硅（硬度9.25），硬度非常接近，日常佩戴不易磨损；\n2. **火彩表现**：莫桑钻的色散值（0.104）高于天然钻石，在阳光下火彩更耀眼；\n3. **品质与证书**：琼华选用的每一颗莫桑石均为 D色/VVS1 级切工，并配备 GRA 独立腰码证书，支持专业复检，请放心选购！';
    } else {
      steps.push({ node: '语义理解', status: 'done', detail: '常规意图应答' });
      reply = '收到您的咨询！小琼随时在为您服务。琼华珠宝坚持选用天然玉石、优质珍珠与切工宝石，支持 7 天无理由退换及终身免费清洗保养。请问您今天想挑选哪类饰品？';
    }

    return Promise.resolve({
      reply: reply,
      trace: steps,
      self_corrected: selfCorrected,
      model: '本地规则引擎（离线降级）',
      backend: 'fallback:local-demo',
      latency_ms: Math.round(performance.now() - t0)
    });
  }

  function localMarketing(req) {
    var t0 = performance.now();
    var pname = (req.product_name || '').trim() || '和田碧玉平安扣吊坠';
    var platform = req.target_platform || 'xiaohongshu';
    var title, content;

    if (platform === 'xiaohongshu') {
      title = '一眼惊艳！被闺蜜追着要链接的【' + pname + '】到底有多绝✨';
      content = '救命！真的没有人能拒绝天然玉石的温润感吧😭\n最近刚入手的这款【' + pname + '】，实物比图片高级一万倍！\n\n🌿 **材质细节**：\n选用温润老料，日光下泛着通透的油脂光泽，戴上瞬间冷白皮拉满！锁骨位置恰到好处，不管是搭法式衬衫还是新中式旗袍都绝配！\n\n💎 **关于品质**：\n每一件都带权威质检证书，真正东方女性骨子里的温润与贵气～\n送长辈或者犒赏自己都体面到不行，百元预算戴出万元质感！\n\n#我的国风穿搭 #小众首饰 #东方美学 #珠宝好物分享 #' + pname;
    } else if (platform === 'douyin') {
      title = '【带货口播脚本】30秒讲透为什么这届年轻人都在戴' + pname + '？';
      content = '【镜头：特写首饰在光下的油脂光泽】\n（主播话术，语速欢快有力）：\n“所有女生！别再买那些戴两次就发黑的合金首饰了！\n看一下我手上这条刚刚从展厅抢出来的——【' + pname + '】！\n\n（展示质检证书与切工细节）：\n天然原矿老料，一石一证，每一件都在一物一拍！\n以前专柜随随便便都要两三千，今天在小琼的直播间，直接把中间商差价砍到底！\n左下角小黄车直接拍，支持全国权威机构复检，假一赔十！3、2、1，上链接！”';
    } else {
      title = '【私域臻品】温润如玉，岁岁平安 —— ' + pname + '年度私享鉴赏';
      content = '尊敬的贵宾客户：\n\n玉能养人，亦能寄托心愿。琼华工坊历时三月精雕细琢，甄选上乘玉料，为您呈献本季限定之作 ——【' + pname + '】。\n\n· 原矿老料手工开相，触手温润如凝脂；\n· 搭配特制国风沉香礼盒，随礼赠定制保养真皮擦布；\n· VIP 私享专线特权，尊享终身免费复检与绳线焕新服务。\n\n愿此玉伴您与家人四季常安，福泽绵长。欢迎垂询您的专属珠宝顾问。';
    }

    var BANNED = [
      { word: '顶级', reason: '违反《新广告法》绝对化极限词', suggest: '高规格 / 典雅品质' },
      { word: '第一', reason: '违反《新广告法》极限用语，禁止排他性宣传', suggest: '名列前茅 / 匠心之选' },
      { word: '绝无仅有', reason: '虚假夸大宣传', suggest: '稀有难得 / 珍藏款' },
      { word: '全网唯一', reason: '不可证实的虚假陈述', suggest: '独具匠心 / 原创设计' },
      { word: '100%保真', reason: '金融担保类承诺，严禁绝对化承诺', suggest: '附权威质检证书 / 假一赔十' },
      { word: '包治百病', reason: '医疗夸大功效违禁词', suggest: '温润养人 / 身心愉悦' }
    ];
    var kw = req.keywords || '';
    var violations = BANNED.filter(function (b) { return pname.indexOf(b.word) >= 0 || kw.indexOf(b.word) >= 0; });
    var score = Math.max(80, 100 - violations.length * 10);

    return Promise.resolve({
      title: title,
      content: content,
      platform: platform,
      compliance: {
        score: score,
        status: violations.length === 0 ? 'PASS' : 'WARNING',
        violations: violations,
        suggestions: violations.length === 0
          ? '文案整体合规度极高，符合各大电商与社交平台内容安全规范。'
          : '注意避免使用绝对化形容词，建议采纳右侧替换建议。'
      },
      latency_ms: Math.round(performance.now() - t0)
    });
  }

  function localAnalysis(req) {
    var t0 = performance.now();
    var q = (req.query_text || '').trim();
    var sql, chart, conclusion, highlight;

    if (q.indexOf('品类') >= 0 || q.indexOf('分类') >= 0) {
      sql = 'SELECT category AS 品类, SUM(amount) AS 销售额, COUNT(*) AS 订单数 FROM orders GROUP BY category ORDER BY 销售额 DESC;';
      chart = { type: 'bar', labels: ['天然玉石吊坠', '莫桑钻饰品', '珍珠首饰', '纯银手镯'], data: [642000, 512000, 485000, 255200] };
      conclusion = '玉石吊坠与莫桑钻贡献了超过 60% 的总营收；纯银手镯本月环比微跌 6.8%，建议结合营销模块开展专场满减引流。';
      highlight = '纯银国风手镯';
    } else if (q.indexOf('渠道') >= 0 || q.indexOf('来源') >= 0) {
      sql = 'SELECT channel AS 获客渠道, SUM(amount) AS 成交额, AVG(amount) AS 客单价 FROM orders GROUP BY channel;';
      chart = { type: 'pie', labels: ['微信私域', '抖音直播', '天猫旗舰'], data: [820000, 640000, 434200] };
      conclusion = '微信私域客单价最高（¥920/单），复购率达 34.6%，是高价值珠宝的核心出货阵地。';
      highlight = '高客单天然翡翠挂件';
    } else {
      sql = "SELECT strftime('%Y-%m', order_date) AS 月份, SUM(amount) AS GMV FROM orders GROUP BY 1 ORDER BY 1 LIMIT 6;";
      chart = { type: 'line', labels: ['5月', '6月', '7月', '8月', '9月', '10月'], data: [240000, 290000, 310000, 330000, 350000, 374200] };
      conclusion = '近 6 个月业务呈现平稳增长态势，复合月环比增长率达到 9.2%，预计第四季度珠宝旺季有望突破 45 万月销大关。';
      highlight = '天然和田玉青海老料吊坠';
    }
    return Promise.resolve({ sql: sql, chart: chart, conclusion: conclusion, highlight_product: highlight, latency_ms: Math.round(performance.now() - t0) });
  }

  /* ---------- 事件总线：真实 SSE 优先，失败降级为示例事件 ---------- */

  // 仅在拿不到后端时使用。界面上会明确标成「示例事件流 · 无后端」，
  // 不会伪装成实时流。
  var SAMPLE_EVENTS = [
    { tag: 'MASTER', level: 'info', msg: 'OmniAgent Platform 统一控制总线初始化完成。' },
    { tag: 'GATEWAY', level: 'info', msg: '流量总线接管，监听 127.0.0.1:8000。' },
    { tag: 'ECOM-AGENT', level: 'info', msg: '珠宝导购 LangGraph 状态机就绪，知识库向量切片预热。' },
    { tag: 'MARKETING', level: 'warn', msg: 'Coze 工作流降级保护加载完成，违禁词库 114 词。' },
    { tag: 'ANALYTICS', level: 'info', msg: 'DuckDB 内存引擎就绪，挂载电商交易数据集 2,450 笔。' },
    { tag: 'HEALTH', level: 'ok', msg: '全局微服务健康巡检完成，核心业务全部响应。' }
  ];

  /**
   * 启动事件总线。
   * handlers = { onEvent(ev, source), onMode('connecting'|'live'|'sample') }
   * 返回 { mode, stop() }。
   *
   * 真实路径：EventSource('/api/v1/events/stream')，后端每 3s 做一次
   *          TCP 端口探测，只把「状态变化」和「巡检心跳」推下来。
   * 降级路径：拿不到后端（GitHub Pages / file:// / 后端未启）→ 播内置示例事件，
   *          并把角标切成「示例事件流 · 无后端」。
   */
  function startEvents(handlers) {
    var h = handlers || {};
    var es = null;
    var state = { mode: 'connecting', stopped: false };

    function fire(ev, source) {
      if (typeof h.onEvent === 'function') {
        try { h.onEvent(ev, source); } catch (e) { /* 渲染异常不影响主流程 */ }
      }
    }
    function setMode(m) {
      if (state.stopped) return;
      state.mode = m;
      if (typeof h.onMode === 'function') {
        try { h.onMode(m); } catch (e) { /* ignore */ }
      }
    }
    function startSample() {
      setMode('sample');
      var i = 0;
      state.sampleTimer = setInterval(function () {
        if (state.stopped) { clearInterval(state.sampleTimer); return; }
        var raw = SAMPLE_EVENTS[i % SAMPLE_EVENTS.length];
        fire({
          ts: new Date().toTimeString().slice(0, 8),
          tag: raw.tag, level: raw.level, msg: raw.msg, sample: true
        }, 'sample');
        i++;
      }, 1400);
    }

    state.stop = function () {
      state.stopped = true;
      if (es) { try { es.close(); } catch (e) { /* ignore */ } }
      if (state.sampleTimer) clearInterval(state.sampleTimer);
    };

    if (typeof EventSource === 'undefined') {   // 极老浏览器
      startSample();
      return state;
    }

    try {
      es = new EventSource('/api/v1/events/stream');
    } catch (e) {
      startSample();
      return state;
    }

    es.onopen = function () { setMode('live'); };
    es.onmessage = function (m) {
      var ev;
      try { ev = JSON.parse(m.data); } catch (e) { return; }
      fire(ev, 'live');
    };
    // EventSource 失败后会自动重连 —— 首次报错就关掉并降级，避免在静态托管上无限刷 404
    es.onerror = function () {
      if (state.stopped) return;
      try { es.close(); } catch (e) { /* ignore */ }
      es = null;
      startSample();
    };

    return state;
  }

  /* ---------- 对外接口 ---------- */
  var OmniAPI = {
    /* 返回 true 表示已连上本地后端 */
    connected: false,

    probe: function () {
      return apiCall('/api/v1/overview/stats')
        .then(function (d) { OmniAPI.connected = true; return d; })
        .catch(function () { OmniAPI.connected = false; return null; });
    },

    startEvents: startEvents,

    guideChat: function (message, history) {
      return apiCall('/api/v1/guide/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, history: history || null })
      }).catch(function () { return localGuideChat(message); });
    },

    marketingGenerate: function (payload) {
      return apiCall('/api/v1/marketing/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).catch(function () { return localMarketing(payload); });
    },

    analysisQuery: function (queryText) {
      return apiCall('/api/v1/analysis/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query_text: queryText })
      }).catch(function () { return localAnalysis({ query_text: queryText }); });
    },

    /* ---------- 2.2 新增：服务起停管控 / 历史曲线 / 事件回放 ---------- */

    /** 起停服务。action: 'stop' | 'start'。
     *  静态模式（无后端）返回明确的 not-available —— 管控是真实进程操作，
     *  没有后端就没有「假装管控」这回事。 */
    controlService: function (id, action) {
      if (!OmniAPI.connected) {
        return Promise.resolve({
          status: 'not-available',
          detail: '当前是静态演示模式（无本地后端）—— 服务起停需要运行 run.bat 启动控制台。'
        });
      }
      return apiCall('/api/v1/services/' + encodeURIComponent(id) + '/' + action, {
        method: 'POST',
        timeoutMs: 15000        // 杀进程要等 3s 超时 + kill，放宽
      });
    },

    /** 历史曲线（在线率 + 延迟）。静态模式返回内置样例曲线，标 sample: true。 */
    fetchHistory: function (minutes) {
      var m = minutes || 60;
      return apiCall('/api/v1/history/probes?minutes=' + m, { timeoutMs: 8000 })
        .catch(function () { return sampleHistory(m); });
    },

    /** 最近事件回放。静态模式返回样例事件，标 sample: true。 */
    fetchRecentEvents: function (limit) {
      var n = limit || 60;
      return apiCall('/api/v1/events/recent?limit=' + n, { timeoutMs: 8000 })
        .catch(function () { return sampleRecentEvents(n); });
    }
  };

  /* ---------- 静态模式的样例历史（明确标注，不冒充实测） ---------- */

  var SAMPLE_SERVICES_META = [
    { id: 'ai-gateway', name: '企业 AI 统一网关', port: 8000 },
    { id: 'ecom-ai-guide', name: '琼华珠宝 AI 智能导购', port: 8001 },
    { id: 'coze-material-studio', name: '多平台爆款素材工作台', port: 8002 },
    { id: 'ai-data-analysis-assistant', name: 'AI 数据分析专家', port: 8510 },
    { id: 'ai-knowledge-assistant', name: '企业级智能知识库 (RAG)', port: 8501 },
    { id: 'data-automation-workbench', name: '自动化情报抓取平台', port: 8765 },
    { id: 'ark_aigc_demo', name: '多模态音视频智能体 (FunClip)', port: 7860 }
  ];

  function sampleHistory(minutes) {
    var n = 48;
    var step = (minutes * 60 / n) * 1000;
    var now = Date.now();
    return Promise.resolve({
      status: 'ok', minutes: minutes, bucket_sec: minutes * 60 / n,
      source: 'sample',
      series: SAMPLE_SERVICES_META.map(function (s, idx) {
        var points = [];
        for (var i = n - 1; i >= 0; i--) {
          var t = Math.round((now - i * step) / 1000) * 1000;
          // 每个服务造一段不同的「下线窗口」，曲线看起来像真实历史
          var offline = (i >= (10 + idx * 4)) && (i <= (13 + idx * 4));
          points.push([t, offline ? 0 : 100, offline ? null : 0.4 + Math.sin(i * 0.7 + idx) * 0.3 + 0.2]);
        }
        return { id: s.id, name: s.name, port: s.port, points: points };
      })
    });
  }

  function sampleRecentEvents(limit) {
    var base = [
      { ts: '23:41:02', tag: 'HEALTH', level: 'err', msg: '多模态音视频智能体 (FunClip)（:7860）状态变化：下线，流量已摘除。' },
      { ts: '23:41:05', tag: 'HEALTH', level: 'ok', msg: '多模态音视频智能体 (FunClip)（:7860）状态变化：上线，已重新纳入调度。' },
      { ts: '23:40:36', tag: 'HEALTH', level: 'info', msg: '全局健康巡检完成，7/7 在线，本轮无状态变化。' },
      { ts: '23:39:12', tag: 'ECOM-AGENT', level: 'ok', msg: '琼华珠宝 AI 智能导购（:8001）已就绪。' },
      { ts: '23:38:59', tag: 'MASTER', level: 'info', msg: '事件总线接入成功：本流由真实 TCP 端口探测驱动，每 3s 巡检一次，当前在线 7/7。' }
    ];
    var events = [];
    for (var i = 0; i < Math.min(limit, 24); i++) {
      var e = Object.assign({}, base[i % base.length]);
      e.sample = true;
      events.push(e);
    }
    return Promise.resolve({ status: 'ok', limit: limit, source: 'sample', events: events });
  }

  window.OmniAPI = OmniAPI;
})();
