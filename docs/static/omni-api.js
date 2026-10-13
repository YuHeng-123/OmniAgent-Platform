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
    var headers = Object.assign({}, (options && options.headers) || {});
    if (typeof window !== 'undefined' && window.OmniStore) {
      try {
        var currentTenant = window.OmniStore.get('tenant') || 'tenant-hq';
        var currentRole = window.OmniStore.get('role') || 'admin';
        headers['X-Tenant-ID'] = currentTenant;
        headers['X-Role'] = currentRole;
        var jwt = window.OmniStore.get('jwtToken');
        if (jwt) {
          headers['Authorization'] = 'Bearer ' + jwt;
        }
      } catch (e) {}
    }
    var opts = Object.assign({}, options || {}, { signal: ctrl.signal, headers: headers });
    delete opts.timeoutMs;
    return fetch(path, opts)
      .then(function (r) {
        if (!r.ok) {
          return r.json().catch(function () { return null; }).then(function (errBody) {
            var err = new Error('HTTP ' + r.status);
            err.status = r.status;
            err.body = errBody;
            throw err;
          });
        }
        return r.json();
      })
      .finally(function () { clearTimeout(timer); });
  }

  /* ---------- 内置演示逻辑：与 server.py 的行为保持一致 ---------- */

  function isLangEn() {
    return typeof window !== 'undefined' && window.OmniStore && window.OmniStore.get('lang') === 'en';
  }

  // 导购知识池（与 server.py GUIDE_PRODUCTS 镜像）
  var GUIDE_PRODUCTS = [
    { tag: '福禄双全', name: '【琼华·福禄双全】天然和田碧玉平安扣吊坠', price: 1680, list: 2399,
      spec: '新疆且末老料，油润细腻，附国家级宝玉石质检证书',
      fit: ['长辈', '妈妈', '婆婆', '平安', '玉'] },
    { tag: '月满西楼', name: '【琼华·月满西楼】天然淡水无瑕珍珠项链', price: 1120, list: 1480,
      spec: '8-9mm 微瑕近圆，正圆强光皮光极亮',
      fit: ['长辈', '妈妈', '婆婆', '优雅', '珍珠', '通勤'] },
    { tag: '星辰大海', name: '【琼华·星辰大海】D色莫桑钻经典六爪戒指', price: 699, list: 2999,
      spec: 'D色/VVS1 切工，GRA 独立腰码证书，火彩直逼天然钻',
      fit: ['女友', '老婆', '求婚', '结婚', '纪念', '戒指', '莫桑'] },
    { tag: '竹报平安', name: '【琼华·竹报平安】天然和田玉青白玉竹节手串', price: 668, list: 880,
      spec: '青白玉竹节雕工，15颗均色，弹力绳双层打结',
      fit: ['自己', '手串', '日常', '玉'] },
    { tag: '鸿运当头', name: '【琼华·鸿运当头】天然南红玛瑙平安无事牌', price: 968, list: 1280,
      spec: '川料柿子红，满色满肉，牌形方正',
      fit: ['爸爸', '男士', '本命年', '转运'] },
    { tag: '映月', name: '【琼华·映月】925银镶和田玉小方牌项链', price: 359, list: 459,
      spec: '入门款，青白玉小方牌+925银链，白领通勤首选',
      fit: ['入门', '学生', '预算', '通勤', '项链'] },
    { tag: '岁岁团圆', name: '【琼华·岁岁团圆】天然珍珠耳钉 7-8mm', price: 528, list: 680,
      spec: '正圆强光，耳针925银，配防丢耳塞',
      fit: ['女友', '老婆', '耳饰', '珍珠', '日常'] },
    { tag: '金玉满堂', name: '【琼华·金玉满堂】足金镶嵌和田玉小吊坠', price: 1688, list: 1980,
      spec: '足金镶口+和田青玉，金玉良缘的经典组合',
      fit: ['金', '贵气', '婚嫁', '妈妈'] }
  ];

  var GUIDE_PRODUCTS_EN = [
    { tag: 'Fortune & Serenity', name: '【Qionghua · Fortune】Natural Hetian Nephrite Jade Donut Pendant', price: 268, list: 380,
      spec: 'Authentic old-mine Hetian jade, oily texture, accompanied by NGTC/GIA lab certificate',
      fit: ['elder', 'mom', 'peace', 'jade', 'heritage'] },
    { tag: 'Moonlit Horizon', name: '【Qionghua · Moonlit】Natural Freshwater Cultured Pearl Strand', price: 165, list: 240,
      spec: '8-9mm near-round, strong metallic mirror luster, sterling clasp',
      fit: ['mother', 'wife', 'elegant', 'pearl', 'commute'] },
    { tag: 'Starlight Solitaire', name: '【Qionghua · Starlight】Classic 6-Prong D-Color Moissanite Ring', price: 99, list: 399,
      spec: 'D-Color / VVS1 cut, laser-inscribed GRA certificate, diamond-rivaling fire',
      fit: ['girlfriend', 'wife', 'proposal', 'engagement', 'ring', 'moissanite'] },
    { tag: 'Serene Bamboo', name: '【Qionghua · Bamboo】Natural Nephrite Bamboo Joint Bracelet', price: 110, list: 160,
      spec: 'Carved bamboo joint beads, uniform green hue, double elastic strung',
      fit: ['daily', 'bracelet', 'jade', 'men'] },
    { tag: 'Scarlet Talisman', name: '【Qionghua · Fortune】Natural South Red Agate Talisman Plaque', price: 140, list: 185,
      spec: 'Vibrant persimmon red, solid core, symmetrical talisman carving',
      fit: ['dad', 'men', 'protection', 'agate'] },
    { tag: 'Crescent Moon', name: '【Qionghua · Crescent】S925 Sterling Inlaid Jade Pendant', price: 55, list: 85,
      spec: 'Entry-level piece, nephrite tablet with sterling chain, modern minimalist wear',
      fit: ['budget', 'entry', 'student', 'commute', 'necklace'] },
    { tag: 'Luminous Studs', name: '【Qionghua · Luminous】7-8mm Cultured Pearl Stud Earrings', price: 79, list: 110,
      spec: 'Round high-luster pearls with S925 anti-loss silicone backs',
      fit: ['girlfriend', 'earrings', 'pearl', 'daily'] },
    { tag: 'Golden Harmony', name: '【Qionghua · Harmony】Solid Gold Inlaid Nephrite Jade Pendant', price: 280, list: 360,
      spec: 'Solid gold bezel + authentic green jade, timeless heirloom craftsmanship',
      fit: ['gold', 'luxury', 'wedding', 'mom'] }
  ];

  function _pickGuideProducts(msg) {
    var isEn = isLangEn();
    var pool = isEn ? GUIDE_PRODUCTS_EN : GUIDE_PRODUCTS;
    var scored = [];
    pool.forEach(function (p) {
      var s = 0;
      p.fit.forEach(function (k) { if (msg.toLowerCase().indexOf(k.toLowerCase()) >= 0) s++; });
      if (s > 0) scored.push({ s: s, p: p });
    });
    scored.sort(function (a, b) { return b.s - a.s; });
    if (scored.length) {
      var top = scored[0].s;
      return scored.filter(function (x) { return x.s === top; }).slice(0, 3).map(function (x) { return x.p; });
    }
    var m = msg.match(/(\d{3,5})/);
    if (m) {
      var budget = parseInt(m[1], 10);
      var inRange = pool.filter(function (p) { return p.price <= budget * 1.2; });
      inRange.sort(function (a, b) { return b.price - a.price; });
      if (inRange.length) return inRange.slice(0, 3);
      return pool.slice().sort(function (a, b) { return a.price - b.price; }).slice(0, 2);
    }
    return [];
  }

  function _recommendHit(msg) {
    var lower = (msg || '').toLowerCase();
    var zhHits = ['推荐', '买', '送', '项链', '手串', '戒指', '玉', '翡翠', '看', '挑'].some(function (k) { return msg.indexOf(k) >= 0; });
    var enHits = ['recommend', 'suggest', 'gift', 'necklace', 'ring', 'pendant', 'jade', 'pearl', 'moissanite', 'diamond', 'buy'].some(function (k) { return lower.indexOf(k) >= 0; });
    return zhHits || enHits;
  }

  function localGuideChat(userMsg) {
    var msg = (userMsg || '').trim();
    var lower = msg.toLowerCase();
    var t0 = performance.now();
    var isEn = isLangEn();

    var isCoupon = ['券', '优惠', '打折', '便宜', '省钱', '满减', 'coupon', 'discount', 'voucher', 'code', 'promo'].some(function (k) { return lower.indexOf(k) >= 0; });
    var isDiff = ['区别', '真假', '莫桑', '培育', '天然', '证书', 'diff', 'diamond', 'moissanite', 'gia', 'gra', 'cert', 'real'].some(function (k) { return lower.indexOf(k) >= 0; });
    var isAfterSales = ['退', '换', '售后', '保修', '维修', '断线', '坏', 'return', 'refund', 'warranty', 'repair', 'broken', 'after-sale'].some(function (k) { return lower.indexOf(k) >= 0; });
    var isCare = ['保养', '清洗', '变黑', '氧化', '佩戴', '护理', '发干', 'care', 'clean', 'tarnish', 'wash', 'maintain', 'wear'].some(function (k) { return lower.indexOf(k) >= 0; });
    var isCompare = (['哪个好', '比', 'vs', '选', '值得', 'compare', 'better', 'choice'].some(function (k) { return lower.indexOf(k) >= 0; })) && (lower.indexOf('玉') >= 0 || lower.indexOf('珍珠') >= 0 || lower.indexOf('jade') >= 0 || lower.indexOf('pearl') >= 0);

    var intentLabel = isCoupon ? 'COUPON_QUERY'
      : isAfterSales ? 'AFTER_SALES'
      : isCare ? 'CARE_GUIDE'
      : isCompare ? 'MATERIAL_COMPARE'
      : isDiff ? 'KNOWLEDGE_QA'
      : (_recommendHit(msg) || _pickGuideProducts(msg).length) ? 'PRODUCT_RECOMMEND'
      : 'KNOWLEDGE_QA';

    var steps = isEn ? [
      { node: 'Intent Router', status: 'done', detail: 'Classified intent: ' + intentLabel },
      { node: 'Hybrid RAG Retrieval', status: 'done', detail: 'Retrieved 4 high-confidence knowledge chunks, max similarity: 0.942' }
    ] : [
      { node: '意图识别 (Router)', status: 'done', detail: '分类为: ' + intentLabel },
      { node: '向量库混合检索 (RAG)', status: 'done', detail: '检索到 4 条高置信度知识切片，相似度最高 0.942' }
    ];
    var selfCorrected = false;
    var reply;

    if (msg.indexOf('500') >= 0 && (isCoupon || lower.indexOf('500') >= 0)) {
      selfCorrected = true;
      if (isEn) {
        steps.push({ node: 'Tool Execution (get_coupon)', status: 'retry', detail: "Calling get_coupon('$500_unconditional') failed: voucher face value exceeds system authorization ceiling" });
        steps.push({ node: '⚡ Self-Correction & Policy Engine', status: 'done', detail: 'Triggered self-correction: auto-downgraded to eligible tiers [$200 off $2,000] and [$50 New Buyer Gift]' });
        reply = 'We apologize for the inconvenience! Our system currently does not offer an unconditional $500 coupon code. However, our luxury concierge has secured the top eligible tiers for your order:\n\n1. **New Buyer Gift**: $50 off orders over $300 (applied automatically at checkout);\n2. **Fine Jewelry VIP Tier**: $200 off orders over $2,000 (valid across all Jadeite, Pearls, and Moissanite)!\n\nFor example, pairing our **Natural Hetian Nephrite Jade Pendant** ($268) with a sterling silver accent easily unlocks the tiered savings. Would you like me to reserve this voucher code for your cart?';
      } else {
        steps.push({ node: '工具调用 (Tool Calling)', status: 'retry', detail: "调用 get_coupon('500元无门槛') 失败：券面额超出系统上限" });
        steps.push({ node: '⚡ 自动反思与自纠错 (Self-Correction)', status: 'done', detail: '触发纠错策略：自动降级检索最接近规则，回正为【满2000减200】与【新人50元立减】' });
        reply = '非常抱歉呀，小琼帮您查了一下，目前店内没有【500元无门槛券】哦～ 不过小琼为您申请到了当前最划算的组合：\n\n1. **新人专享礼**：满 300 减 50 元立减券；\n2. **珠宝品类大额券**：满 2000 减 200 元满减券！\n\n如果您今天选购【天然和田玉青海老料吊坠】（原价 ¥1,880），再凑单一个小银饰，即可直接立减 200 元，非常划算！需要我帮您锁定领券名额吗？';
      }
    } else if (isCoupon) {
      if (isEn) {
        steps.push({ node: 'Tool Calling (list_coupons)', status: 'done', detail: 'Executed list_coupons(active=True), returned 2 active codes + 1 VIP live voucher tier' });
        reply = 'Here are the active stackable offers currently available on Qionghua Global DTC:\n\n1. **New Buyer Gift**: $50 off orders over $300 (auto-applied at checkout);\n2. **Fine Jewelry VIP Tier**: $200 off orders over $2,000 across jade and pearls;\n3. **Concierge Secret Code**: Live stream code **LUXURY88** provides an additional 12% off.\n\nWould you like me to configure a curated package tailored to your budget?';
      } else {
        steps.push({ node: '工具调用 (Tool Calling)', status: 'done', detail: '执行 list_coupons(active=True)，返回 2 张可用券 + 1 条直播福袋规则' });
        reply = '现在店内能叠的优惠小琼帮您理好了：\n\n1. **新人专享礼**：满 300 减 50 元立减券（下单页自动带出）；\n2. **珠宝品类大额券**：满 2000 减 200 元，玉石/珍珠通用；\n3. **私域暗号**：直播间蹲「整点福袋」，可抽 88 折码，与大额券二选一不叠加。\n\n搭配建议：选【映月】925银镶和田玉方牌（¥359）可直接用新人券；两件拼到 ¥2,000 用大额券最划算。需要我按您的预算配个组合吗？';
      }
    } else if (isAfterSales) {
      if (isEn) {
        steps.push({ node: 'Tool Calling (query_policy)', status: 'done', detail: 'Executed query_after_sales_policy(), matched Global White-Glove Warranty v3.2' });
        reply = 'Here is our overseas white-glove warranty and return policy:\n\n1. **30-Day Hassle-Free Returns**: Eligible for unworn jewelry with security tags intact, with prepaid return shipping labels;\n2. **1-Year Complimentary Warranty**: Complimentary restringing and prong maintenance for all artisanal pieces;\n3. **Lifetime Spa & Care**: Free sonic cleaning, re-polishing, and earring post replacements worldwide;\n4. **Dual Authentication**: Each jewel ships with NGTC/GRA certification, guaranteed authentic.\n\nWould you like to initiate a return or request a complimentary jewelry spa service?';
      } else {
        steps.push({ node: '工具调用 (Tool Calling)', status: 'done', detail: '执行 query_after_sales_policy()，命中《售后服务手册 v3.2》4 条' });
        reply = '小琼把售后政策给您讲清楚，放心买：\n\n1. **7 天无理由退换**：签收起 7 天内、吊牌完好的都可退换，店铺运费险已默认勾选；\n2. **1 年免费质保**：绳线老化、佩戴中断线，免费换新绳并重新手工编织；\n3. **终身免费养护**：清洗、抛光、换耳针，寄回或到店都行；\n4. **证书复验**：每件附国家级 CMA/CNAS 质检证书，支持任何权威机构复检，假一赔十。\n\n您是想办理退换，还是想给手上的宝贝做个养护？';
      }
    } else if (isCare) {
      var pearl = lower.indexOf('珍珠') >= 0 || lower.indexOf('pearl') >= 0;
      if (isEn) {
        steps.push({ node: 'Knowledge Retrieval (RAG)', status: 'done', detail: 'Matched jewelry care chunk #' + (pearl ? '117: Organic Pearl Care' : '092: Jadeite & Nephrite Maintenance') });
        reply = pearl
          ? 'Pearls are delicate organic gemstones. Remember "Last on, First off":\n\n1. Put pearls on AFTER makeup and perfume to prevent organic luster erosion;\n2. Gently wipe with the provided microfiber cloth before storing flat in velvet boxes;\n3. Never hang on hooks or submerge in sonic cleaners.'
          : 'Caring for natural jadeite & nephrite:\n\n1. Avoid violent impacts and chemical agents;\n2. Regular wear enhances jade\'s natural luster from skin oils ("living stone" tradition);\n3. Clean gently with lukewarm water and a soft cloth.';
      } else {
        steps.push({ node: '知识检索 (RAG)', status: 'done', detail: '命中《珠宝养护百科》切片 #' + (pearl ? '117：珍珠（有机宝石）养护' : '092：和田玉日常养护') });
        reply = pearl
          ? '珍珠是有机宝石，比玉石更娇贵，记住「后戴先摘」四个字：\n\n1. 化妆、喷香水**之后**再戴——汗液与化妆品的酸碱会蚀损珍珠层；\n2. 回家卸妆**之前**先摘，用眼镜布这类软布干擦汗渍；\n3. 存放时平铺在绒布盒里，**别挂在钩上**（珠层怕拉丝）；\n4. 忌直接水洗——项链绳线遇水易松，脏了寄回，免费做超声波护理。'
          : '玉石保养记住「三避一养」就够了：\n\n1. **避磕碰**：玉硬度高但脆，运动、健身、做家务建议取下；\n2. **避化学品**：香水、洗手液会慢慢蚀损光泽，护肤化妆完成后再佩戴；\n3. **避高温暴晒**：长期暴晒会让玉「失水」发干，洗澡温泉记得摘；\n4. **常佩戴是最好的养玉**：人体油脂让玉越来越温润，「人养玉三年，玉养人一生」。\n\n日常用软布蘸清水擦干即可，**忌超声波机洗**。到店可免费做一次深度养护～';
      }
    } else if (isCompare) {
      if (isEn) {
        steps.push({ node: 'Knowledge Retrieval (RAG)', status: 'done', detail: 'Matched selection guide chunk #402: Jadeite vs Organic Pearls' });
        reply = 'Many clients weigh between jade and pearls. Here is how they compare by setting:\n\n- **Gifts for Elders & Auspicious Heritage** -> Choose Nephrite Jade. Timeless serenity with the classic Donut amulet;\n- **Everyday Office & Versatile Elegance** -> Choose Pearls. High metallic luster brightens skin tones effortlessly;\n- **Budget $200-$400** -> Pearl studs or jade bead cuffs; **Budget $1,000+** -> Heritage nephrite pendant or multi-strand pearl choker.\n\nWhich fine piece would you like to explore first?';
      } else {
        steps.push({ node: '知识检索 (RAG)', status: 'done', detail: '命中珠宝百科切片 #402：《选品指南：玉石 vs 有机宝石》' });
        reply = '很多顾客在玉和珍珠之间纠结，其实看场景就清楚了：\n\n- **送长辈、讲平安寓意** → 选玉。和田玉温润内敛，平安扣、无事牌都是经典；\n- **日常通勤、气质百搭** → 选珍珠。正圆强光最抬气色，衬衫针织全适配；\n- **预算 500-800** → 珍珠耳钉或玉手串最从容；**预算 1500+** → 碧玉吊坠、珍珠项链一步到位。\n\n当然不少老客是「左手玉、右手珠」都收 😊 您想先看哪一类？';
      }
    } else if (isDiff) {
      if (isEn) {
        steps.push({ node: 'Knowledge Retrieval (RAG)', status: 'done', detail: 'Matched domain knowledge chunk #381: Moissanite Optics & Physical Durability vs Mined Diamonds' });
        reply = 'Here is an expert comparison regarding Moissanite vs. Natural Diamonds:\n\n1. **Physical Hardness**: Natural diamond is pure carbon (Mohs 10). Moissanite is silicon carbide (Mohs 9.25), second only to diamond, ensuring permanent brilliance without scuffing or clouding;\n2. **Optical Brilliance**: Moissanite delivers a dispersion rate of 0.104—over 2.4x the fire of mined diamond—radiating captivating rainbow fire under direct light;\n3. **Quality & Authentication**: Every Qionghua Moissanite gemstone is certified D Color / VVS1 clarity with a laser-inscribed GRA certificate for complete authenticity.';
      } else {
        steps.push({ node: '知识检索 (RAG)', status: 'done', detail: '命中珠宝百科知识切片 #381：《莫桑钻与天然钻石光学特质比对》' });
        reply = '这是很多顾客关心的专业问题，小琼为您通俗解答：\n\n1. **物理成分**：天然钻石是纯碳晶体（硬度10）；莫桑石是碳化硅（硬度9.25），硬度非常接近，日常佩戴不易磨损；\n2. **火彩表现**：莫桑钻的色散值（0.104）高于天然钻石，在阳光下火彩更耀眼；\n3. **品质与证书**：琼华选用的每一颗莫桑石均为 D色/VVS1 级切工，并配备 GRA 独立腰码证书，支持专业复检，请放心选购！';
      }
    } else {
      var picks = _pickGuideProducts(msg);
      if (picks.length) {
        if (isEn) {
          steps.push({ node: 'Tool Execution (query_products)', status: 'done', detail: 'Executed query_products(keywords="' + msg.slice(0, 15) + '"), matched ' + picks.length + ' items' });
          steps.push({ node: 'Decision Synthesis (LLM)', status: 'done', detail: 'Synthesized luxury concierge recommendations by budget and occasion' });
          var iconsEn = ['🌟', '💍', '📿'];
          var linesEn = ['Based on your requirements, here are our top curated recommendations:', ''];
          picks.forEach(function (p, i) {
            linesEn.push(iconsEn[i % iconsEn.length] + ' **' + p.name + '**');
            linesEn.push('- ' + p.spec);
            linesEn.push('- Regular Price $' + p.list.toLocaleString() + ' | **Exclusive DTC Price: $' + p.price.toLocaleString() + '**');
            linesEn.push('');
          });
          linesEn.push('Which piece catches your eye? I can share certificates, carat specifications, or styling recommendations.');
          reply = linesEn.join('\n').replace(/\n+$/, '');
        } else {
          steps.push({ node: '工具调用 (Tool Calling)', status: 'done', detail: '执行 query_products(keywords="' + msg.slice(0, 12) + '")，命中 ' + picks.length + ' 款商品' });
          steps.push({ node: '决策合成 (Synthesis)', status: 'done', detail: '结合送礼/自戴场景与预算，生成亲和力导购话术' });
          var icons = ['🌟', '💍', '📿'];
          var lines = ['按您提到的需求，小琼挑了这几款最合适的：', ''];
          picks.forEach(function (p, i) {
            lines.push(icons[i % icons.length] + ' **' + p.name + '**');
            lines.push('- ' + p.spec);
            lines.push('- 专柜价 ¥' + p.list.toLocaleString() + ' ｜ **限时到手价：¥' + p.price.toLocaleString() + '**');
            lines.push('');
          });
          lines.push('您更中意哪一款？我可以帮您把参数、证书样张再展开讲讲～');
          reply = lines.join('\n').replace(/\n+$/, '');
        }
      } else {
        if (isEn) {
          steps.push({ node: 'Semantic Intent Understanding', status: 'done', detail: 'Standard concierge query response' });
          reply = 'Welcome to Qionghua Global Luxury DTC 🌸 I am your AI Jewelry Concierge. I can assist you with: curating fine jewelry by budget, explaining GIA/GRA certifications and gemstone optics, verifying coupon tiers, and arranging worldwide insured courier delivery. What fine jewelry piece may I show you today?';
        } else {
          steps.push({ node: '语义理解', status: 'done', detail: '常规意图应答' });
          var welcomePool = [
            '收到您的咨询！小琼随时在为您服务。琼华珠宝坚持选用天然玉石、优质珍珠与切工宝石，支持 7 天无理由退换及终身免费清洗保养。请问您今天想挑选哪类饰品？',
            '您好呀～小琼在的。无论想找送长辈的平安扣、送爱人的珍珠，还是日常戴的入门款，告诉我场合和预算，我来帮您配三套方案。也可以直接问我优惠、售后和保养～',
            '欢迎光临琼华珠宝 🌸 小琼可以帮您：按预算选款、讲清证书与材质、查优惠组合、安排售后养护。您先说说想看哪一类？'
          ];
          reply = welcomePool[msg.length % welcomePool.length];
        }
      }
    }

    return Promise.resolve({
      reply: reply,
      trace: steps,
      self_corrected: selfCorrected,
      model: isEn ? 'Local Rule Engine (Offline Fallback)' : '本地规则引擎（离线降级）',
      backend: 'fallback:local-demo',
      latency_ms: Math.round(performance.now() - t0)
    });
  }

  // 违禁词库（与 server.py BANNED_WORDS_DB 镜像，30 条，改动请两边同步）
  var BANNED_WORDS_DB = [
    // 《广告法》绝对化极限词
    { word: '顶级', reason: '违反《新广告法》绝对化极限词', suggest: '高规格 / 典雅品质' },
    { word: '第一', reason: '违反《新广告法》极限用语，禁止排他性宣传', suggest: '名列前茅 / 匠心之选' },
    { word: '最好', reason: '违反《广告法》绝对化用语', suggest: '品质出众' },
    { word: '最佳', reason: '违反《广告法》绝对化用语', suggest: '出色之选' },
    { word: '最高级', reason: '《广告法》明令禁止用语', suggest: '高级感 / 轻奢质感' },
    { word: '国家级', reason: '《广告法》禁止的无依据等级用语', suggest: '权威认证（附证书编号）' },
    { word: '世界级', reason: '无依据的等级用语', suggest: '国际水准设计' },
    { word: '绝无仅有', reason: '虚假夸大宣传', suggest: '稀有难得 / 珍藏款' },
    { word: '全网唯一', reason: '不可证实的虚假陈述', suggest: '独具匠心 / 原创设计' },
    { word: '全网最低', reason: '价格绝对化承诺，无法证实', suggest: '限时优惠价' },
    { word: '销量第一', reason: '排他性数据宣传，需权威数据支撑', suggest: '热销口碑款' },
    { word: '永久', reason: '绝对化承诺，不可证实', suggest: '长期有效' },
    { word: '永远', reason: '绝对化承诺', suggest: '长久相伴' },
    // 质量与承诺类
    { word: '100%保真', reason: '金融担保类承诺，严禁绝对化承诺', suggest: '附权威质检证书 / 假一赔十' },
    { word: '假一赔万', reason: '赔付承诺过度，超出可履行范围', suggest: '假一赔十（写入售后条款）' },
    { word: '纯天然无添加', reason: '绝对化质量承诺', suggest: '天然原矿（附证书）' },
    { word: '无效退款', reason: '功效类退款承诺', suggest: '不满意支持 7 天退换' },
    { word: '稳赚', reason: '投资回报承诺，涉金融风险', suggest: '具有收藏价值' },
    { word: '升值', reason: '投资收益承诺，不可证实', suggest: '具有收藏潜力' },
    // 医疗 / 功效类
    { word: '包治百病', reason: '医疗夸大功效违禁词', suggest: '温润养人 / 身心愉悦' },
    { word: '抗衰老', reason: '医疗功效宣传，饰品不具备', suggest: '温润养人' },
    { word: '立即见效', reason: '功效承诺', suggest: '佩戴体验佳' },
    { word: '保平安', reason: '功效承诺（平台敏感词）', suggest: '平安寓意' },
    // 封建迷信类（平台明令）
    { word: '辟邪', reason: '封建迷信宣传，平台禁止', suggest: '祈福寓意' },
    { word: '开光', reason: '封建迷信宣传，平台禁止', suggest: '祈愿主题设计' },
    { word: '镇宅', reason: '封建迷信宣传', suggest: '居家陈设雅趣' },
    { word: '招财', reason: '迷信功效宣传（部分平台禁）', suggest: '美好寓意' },
    // 虚假渊源 / 出身类（珠宝行业高发）
    { word: '祖传', reason: '虚构渊源宣传', suggest: '传统工艺' },
    { word: '宫廷御用', reason: '虚假出身宣传', suggest: '宫廷风设计' },
    { word: '包老', reason: '年代不可证实的宣传', suggest: '经典器形' }
  ];

  var BANNED_WORDS_DB_EN = [
    { word: '100% cure', reason: 'FTC prohibition on unsubstantiated health and medical claims', suggest: 'Wellness aesthetics' },
    { word: 'guaranteed profit', reason: 'SEC/FTC deceptive investment gain representation', suggest: 'Cherished heirloom value' },
    { word: 'world\'s best', reason: 'Puffery without third-party comparative audit backing', suggest: 'Signature craftsmanship' },
    { word: 'cheapest ever', reason: 'Substantiation failure for absolute pricing guarantees', suggest: 'Exclusive seasonal rate' },
    { word: 'ward off evil', reason: 'Social platform policy on superstitious and mystical claims', suggest: 'Heritage blessing motif' }
  ];

  function localMarketing(req) {
    var t0 = performance.now();
    var isEn = isLangEn();
    var pname = (req.product_name || '').trim() || (isEn ? 'Moissanite Solitaire Engagement Ring' : '和田碧玉平安扣吊坠');
    var platform = req.target_platform || 'xiaohongshu';
    var title, content;

    if (isEn) {
      if (platform === 'xiaohongshu') {
        title = 'Elegance Redefined · Why Everyone is Asking About The [' + pname + '] ✨';
        content = 'Obsessed with this effortless glow 😭\nJust unboxed the new [' + pname + '], and it is tenfold more breathtaking in person!\n\n🌿 **Craftsmanship & Details**:\nFeaturing certified old-mine natural stone with radiant luster under sunlight. Styled seamlessly with linen blouses or evening slip dresses.\n\n💎 **Certified Luxury**:\nAccompanied by an individual gemological certificate. Pure understated luxury without the traditional retail markup.\n\n#FineJewelry #DTCJewelry #MoissaniteRing #QuietLuxury #OOTD #' + pname.replace(/[\s·【】\[\]]/g, '');
      } else if (platform === 'douyin') {
        title = '[Viral Hook Script] 30s Breakdown: Why Gen Z is Ditching Mined Diamonds for ' + pname + '?';
        content = '[Visual: 4K macro lens sweep across facet dispersion]\n(Host / Voiceover - Energetic & Confident):\n"Stop overpaying 10x for mined diamonds that lose half their value at checkout!\nLook at this piece right here—the newly certified [' + pname + ']!\n\n[Zoom into GRA certificate laser inscription]:\nD-Color, VVS1 clarity, and passes electronic diamond testers in 1 second flat!\nTap the showcase link below—insured worldwide express shipping with full 30-day money-back guarantee. In 3, 2, 1, grab yours before this holiday drop sells out!"';
      } else if (platform === 'wechat') {
        title = '[VIP Private Client Preview] Timeless Splendor —— ' + pname + ' Annual Capsule Release';
        content = 'Dear VIP Client,\n\nTrue luxury lies in enduring grace. The Qionghua Atelier is delighted to present our private capsule release —— [' + pname + '].\n\n· Hand-selected raw gemstone polished to silken tactile perfection;\n· Housed in our bespoke sandalwood presentation chest with microfiber spa kit;\n· Dedicated VIP concierge line with complimentary lifetime re-polishing and re-stringing.\n\nMay this jewel bring timeless serenity to you and your loved ones. Please reply to reserve your numbered edition.';
      } else if (platform === 'tmall') {
        title = '[Qionghua Haute Joaillerie] ' + pname + ' —— Certified Authenticity & Ethical Brilliance';
        content = '[Product Highlights]\n· ' + ((req.selling_points || '').trim() || 'Certified Raw Gemstone · Artisanal Handcraft · Individual Lab Certification') + '\n· Accompanied by official NGTC/GIA/GRA certificate with online registry lookup\n\n[Specifications]\n· Materials: Certified Moissanite / Grade-A Jadeite / Cultured Pearls | Metal: S925 Platinum Plated / 18K Solid Gold\n· Included: Luxury Presentation Box + Velvet Travel Pouch + Polishing Cloth + Certificate Card\n\n[White-Glove Services]\n✓ 30-Day Hassle-Free Returns with complimentary return labels\n✓ 1-Year Free Restringing & Lifetime Sonic Cleaning Spa\n✓ Dispatched within 24 hours via DHL/FedEx Insured Worldwide Shipping';
      } else if (platform === 'moments') {
        title = 'Everyday Luxury Curation · ' + pname;
        content = 'Subtle sparkle for the everyday capsule wardrobe. [' + pname + '] is that one staple you never take off ✨ #MinimalistJewelry #RingInspo';
      }
    } else {
      if (platform === 'xiaohongshu') {
        title = '一眼惊艳！被闺蜜追着要链接的【' + pname + '】到底有多绝✨';
        content = '救命！真的没有人能拒绝天然玉石的温润感吧😭\n最近刚入手的这款【' + pname + '】，实物比图片高级一万倍！\n\n🌿 **材质细节**：\n选用温润老料，日光下泛着通透的油脂光泽，戴上瞬间冷白皮拉满！锁骨位置恰到好处，不管是搭法式衬衫还是新中式旗袍都绝配！\n\n💎 **关于品质**：\n每一件都带权威质检证书，真正东方女性骨子里的温润与贵气～\n送长辈或者犒赏自己都体面到不行，百元预算戴出万元质感！\n\n#我的国风穿搭 #小众首饰 #东方美学 #珠宝好物分享 #' + pname;
      } else if (platform === 'douyin') {
        title = '【带货口播脚本】30秒讲透为什么这届年轻人都在戴' + pname + '？';
        content = '【镜头：特写首饰在光下的油脂光泽】\n（主播话术，语速欢快有力）：\n“所有女生！别再买那些戴两次就发黑的合金首饰了！\n看一下我手上这条刚刚从展厅抢出来的——【' + pname + '】！\n\n（展示质检证书与切工细节）：\n天然原矿老料，一石一证，每一件都在一物一拍！\n以前专柜随随便便都要两三千，今天在小琼的直播间，直接把中间商差价砍到底！\n左下角小黄车直接拍，支持全国权威机构复检，假一赔十！3、2、1，上链接！”';
      } else if (platform === 'wechat') {
        title = '【私域臻品】温润如玉，岁岁平安 —— ' + pname + '年度私享鉴赏';
        content = '尊敬的贵宾客户：\n\n玉能养人，亦能寄托心愿。琼华工坊历时三月精雕细琢，甄选上乘玉料，为您呈献本季限定之作 ——【' + pname + '】。\n\n· 原矿老料手工开相，触手温润如凝脂；\n· 搭配特制国风沉香礼盒，随礼赠定制保养真皮擦布；\n· VIP 私享专线特权，尊享终身免费复检与绳线焕新服务。\n\n愿此玉伴您与家人四季常安，福泽绵长。欢迎垂询您的专属珠宝顾问。';
      } else if (platform === 'tmall') {
        title = '【琼华甄选】' + pname + ' —— 一证一物，戴得放心';
        content = '【商品亮点】\n· ' + ((req.selling_points || '').trim() || '原矿老料 · 手工精雕 · 一物一证') + '\n· 权威机构质检证书随货同行，支持任意权威机构复检\n\n【参数规格】\n· 材质：天然和田玉 / 淡水珍珠 / 莫桑石（按款）｜金属：S925 / 足金镶口\n· 赠品：东方国风锦盒 + 沉香香片 + 专业擦玉布 + 证书保护套\n\n【贴心服务】\n✓ 7 天无理由退换（吊牌完好），运费险默认赠送\n✓ 1 年免费换绳织补，终身免费清洗养护\n✓ 收货后 48 小时内发货，顺丰保价包邮\n\n【温馨提示】玉石色泽自然天成，同一块料不同光线下呈现略有差异，实物为准。';
      } else if (platform === 'moments') {
        title = '朋友圈日常分享 · ' + pname;
        content = '老客都懂，一年就开两次的玉料 😊\n【' + pname + '】到货实拍，日光下没加滤镜。\n\n· 温润挂，上手比照片好看十倍\n· 证书齐全，支持复检（不接受验货可以退）\n· 这批只有 12 件，老规矩：老客优先，先到先挑\n\n私信我发细节图，暗号「看货」📖';
      }
    }

    var kw = req.keywords || '';
    var hay = pname + '|' + kw + '|' + title + '|' + content;
    var violations = (isEn ? BANNED_WORDS_DB_EN : BANNED_WORDS_DB).filter(function (b) { return hay.toLowerCase().indexOf(b.word.toLowerCase()) >= 0; });
    var score = Math.max(60, 100 - violations.length * 10);

    return Promise.resolve({
      title: title,
      content: content,
      platform: platform,
      compliance: {
        score: score,
        status: violations.length === 0 ? 'PASS' : 'WARNING',
        violations: violations,
        suggestions: violations.length === 0
          ? (isEn ? 'Copywriting complies with FTC and global advertising standards.' : '文案整体合规度极高，符合各大电商与社交平台内容安全规范。')
          : (isEn ? 'Avoid ungrounded absolute representations; review suggestions on the right.' : '注意避免使用绝对化形容词，建议采纳右侧替换建议。')
      },
      latency_ms: Math.round(performance.now() - t0)
    });
  }

  function localAnalysis(req) {
    var t0 = performance.now();
    var q = (req.query_text || '').trim();
    var lower = q.toLowerCase();
    var isEn = isLangEn();
    var sql, chart, conclusion, highlight;

    if (lower.indexOf('品类') >= 0 || lower.indexOf('分类') >= 0 || lower.indexOf('category') >= 0) {
      if (isEn) {
        sql = 'SELECT category, SUM(amount) AS revenue, COUNT(*) AS orders FROM orders GROUP BY category ORDER BY revenue DESC;';
        chart = { type: 'bar', labels: ['Nephrite Jade Pendants', 'Moissanite Rings', 'Freshwater Pearls', 'Silver Cuffs'], data: [642000, 512000, 485000, 255200] };
        conclusion = 'Nephrite jade pendants and moissanite rings contribute over 60% of total revenue. Silver cuffs contracted 6.8% MoM; recommend cross-marketing bundle campaigns.';
        highlight = 'Sterling Silver Filigree Cuff';
      } else {
        sql = 'SELECT category AS 品类, SUM(amount) AS 销售额, COUNT(*) AS 订单数 FROM orders GROUP BY category ORDER BY 销售额 DESC;';
        chart = { type: 'bar', labels: ['天然玉石吊坠', '莫桑钻饰品', '珍珠首饰', '纯银手镯'], data: [642000, 512000, 485000, 255200] };
        conclusion = '玉石吊坠与莫桑钻贡献了超过 60% 的总营收；纯银手镯本月环比微跌 6.8%，建议结合营销模块开展专场满减引流。';
        highlight = '纯银国风手镯';
      }
    } else if (lower.indexOf('渠道') >= 0 || lower.indexOf('来源') >= 0 || lower.indexOf('channel') >= 0) {
      if (isEn) {
        sql = 'SELECT channel, SUM(amount) AS revenue, AVG(amount) AS aov FROM orders GROUP BY channel;';
        chart = { type: 'pie', labels: ['VIP Private Concierge', 'TikTok Shop Live', 'Shopify Flagship'], data: [820000, 640000, 434200] };
        conclusion = 'VIP Private Concierge achieved highest AOV ($131.4) and 34.6% repurchase rate, representing core luxury retention.';
        highlight = 'High-End Natural Jadeite Pendant';
      } else {
        sql = 'SELECT channel AS 获客渠道, SUM(amount) AS 成交额, AVG(amount) AS 客单价 FROM orders GROUP BY channel;';
        chart = { type: 'pie', labels: ['微信私域', '抖音直播', '天猫旗舰'], data: [820000, 640000, 434200] };
        conclusion = '微信私域客单价最高（¥920/单），复购率达 34.6%，是高价值珠宝的核心出货阵地。';
        highlight = '高客单天然翡翠挂件';
      }
    } else if (lower.indexOf('客单') >= 0 || lower.indexOf('复购') >= 0 || lower.indexOf('aov') >= 0 || lower.indexOf('repurchase') >= 0) {
      if (isEn) {
        sql = 'SELECT channel, ROUND(AVG(amount),1) AS aov, ROUND(SUM(CASE WHEN is_repurchase=1 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS repurchase_rate FROM orders GROUP BY channel;';
        chart = { type: 'bar', labels: ['VIP Private Concierge', 'TikTok Shop Live', 'Shopify Flagship'], data: [920, 640, 588] };
        conclusion = 'VIP Private Concierge leads with AOV $131.4 and 34.6% repurchase rate. Live shopping excels at acquisition but lags retention; embed concierge VIP registration in video scripts.';
        highlight = 'VIP Bespoke High Jewelry';
      } else {
        sql = 'SELECT channel AS 渠道, ROUND(AVG(amount),1) AS 客单价, ROUND(SUM(CASE WHEN is_repurchase=1 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS 复购率 FROM orders GROUP BY channel;';
        chart = { type: 'bar', labels: ['微信私域', '抖音直播', '天猫旗舰'], data: [920, 640, 588] };
        conclusion = '私域客单价 ¥920、复购率 34.6% 双第一；直播间拉新强但留存弱（复购 22.1%），建议直播话术固定埋点「加企微领保养券」，把公域流量沉到私域。';
        highlight = '私域专供高定款';
      }
    } else if (lower.indexOf('top') >= 0 || lower.indexOf('最畅销') >= 0 || lower.indexOf('爆款') >= 0 || lower.indexOf('排行') >= 0 || lower.indexOf('bestsell') >= 0) {
      if (isEn) {
        sql = 'SELECT product_name, SUM(qty) AS units_sold, SUM(amount) AS revenue FROM orders GROUP BY product_name ORDER BY revenue DESC LIMIT 5;';
        chart = { type: 'bar', labels: ['Jade Donut Pendant', 'Moissanite Solitaire Ring', 'Pearl Necklace', 'Bamboo Bracelet', 'Red Agate Plaque'], data: [186000, 152000, 141000, 96000, 88000] };
        conclusion = 'Jade Donut Pendant leads sales for 3 consecutive months; Moissanite rings grew 2.4x via TikTok live but have lower margins; keep ad budget on high-margin jade.';
        highlight = 'Natural Hetian Jade Donut Pendant';
      } else {
        sql = 'SELECT product_name AS 商品, SUM(qty) AS 销量, SUM(amount) AS 销售额 FROM orders GROUP BY product_name ORDER BY 销售额 DESC LIMIT 5;';
        chart = { type: 'bar', labels: ['碧玉平安扣', '莫桑六爪戒指', '珍珠项链', '竹节手串', '南红无事牌'], data: [186000, 152000, 141000, 96000, 88000] };
        conclusion = '碧玉平安扣连续 3 个月销冠，是利润基本盘；莫桑戒指靠直播翻 2.4 倍但毛利偏低，定位引流款，不要占用核心玉石的推广预算。';
        highlight = '天然和田碧玉平安扣';
      }
    } else if (lower.indexOf('新客') >= 0 || lower.indexOf('会员') >= 0 || lower.indexOf('用户') >= 0 || lower.indexOf('growth') >= 0) {
      if (isEn) {
        sql = "SELECT strftime('%Y-%m', first_order_date) AS month, COUNT(*) AS new_buyers FROM customers GROUP BY 1 ORDER BY 1 LIMIT 6;";
        chart = { type: 'line', labels: ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'], data: [310, 345, 380, 412, 438, 465] };
        conclusion = 'New buyer acquisition grew +8.4% MoM, with 60% driven by TikTok Shop; VIP repurchases account for 41% total GMV.';
        highlight = 'New Buyer Welcome SKU';
      } else {
        sql = "SELECT strftime('%Y-%m', first_order_date) AS 月份, COUNT(*) AS 新客数 FROM customers GROUP BY 1 ORDER BY 1 LIMIT 6;";
        chart = { type: 'line', labels: ['5月', '6月', '7月', '8月', '9月', '10月'], data: [310, 345, 380, 412, 438, 465] };
        conclusion = '新客月均增速 +8.4%，六成来自抖音直播间；会员复购贡献 41% GMV。建议把「新人 50 元券」与私域入会动作绑定，先入会再发券。';
        highlight = '新人首单引流款';
      }
    } else {
      if (isEn) {
        sql = "SELECT strftime('%Y-%m', order_date) AS month, SUM(amount) AS gmv FROM orders GROUP BY 1 ORDER BY 1 LIMIT 6;";
        chart = { type: 'line', labels: ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'], data: [240000, 290000, 310000, 330000, 350000, 374200] };
        conclusion = 'Business maintained consistent growth over past 6 months with 9.2% compound monthly growth rate. Q4 holiday peak season expected to surpass $50K monthly GMV. Try querying: Category Breakdown / Acquisition Channels / AOV & Repurchase / Top Sellers / Monthly Growth.';
        highlight = 'Natural Hetian Jade Donut Pendant';
      } else {
        sql = "SELECT strftime('%Y-%m', order_date) AS 月份, SUM(amount) AS GMV FROM orders GROUP BY 1 ORDER BY 1 LIMIT 6;";
        chart = { type: 'line', labels: ['5月', '6月', '7月', '8月', '9月', '10月'], data: [240000, 290000, 310000, 330000, 350000, 374200] };
        conclusion = '近 6 个月业务呈现平稳增长态势，复合月环比增长率达到 9.2%，预计第四季度珠宝旺季有望突破 45 万月销大关。试试问我：品类结构 / 渠道分布 / 客单价与复购 / 爆款排行 / 新客趋势 / 退款率 / 环比增长。';
        highlight = '天然和田玉青海老料吊坠';
      }
    }
    return Promise.resolve({ sql: sql, chart: chart, conclusion: conclusion, highlight_product: highlight, metrics_source: 'demo-sample', latency_ms: Math.round(performance.now() - t0) });
  }

  /* ---------- 网关容灾本地仿真：与 server.py FAILOVER_SCENARIOS 镜像，轮换逻辑一致 ---------- */
  var FAILOVER_SCENARIOS = [
    { scenario: 'upstream-timeout', event: 'CIRCUIT_BREAKER_TRIGGERED',
      primary_status: '504 Gateway Timeout (Simulated)',
      primary_detail: '上游主模型响应超时(>3000ms)，触发熔断阈值',
      failover_model: '本地兜底规则引擎 (Mock Fallback)', failover_status: '200 OK',
      switch_note: '热切至本地兜底规则引擎，业务无感重试成功' },
    { scenario: 'rate-limit', event: 'RATE_LIMIT_SHIFT_TRIGGERED',
      primary_status: '429 Too Many Requests (Simulated)',
      primary_detail: '上游主模型触发 429 限流（令牌桶耗尽），进入冷却窗口',
      failover_model: '备用线路 · 低配模型池 (Mock Backup Pool)', failover_status: '200 OK',
      switch_note: '按预设权重把新请求分流至备用模型池，在途请求原样返回' },
    { scenario: 'quality-degrade', event: 'QUALITY_DEGRADE_TRIGGERED',
      primary_status: '200 OK but quality score < 0.6 (Simulated)',
      primary_detail: '主模型返回 200 但输出质量评分跌破阈值（截断/乱码特征）',
      failover_model: '备用线路 · 重试至主模型备份实例', failover_status: '200 OK (regenerated)',
      switch_note: '静默重新生成一次并校验评分，通过后返回，用户端无感知' }
  ];

  var FAILOVER_SCENARIOS_EN = [
    { scenario: 'upstream-timeout', event: 'CIRCUIT_BREAKER_TRIGGERED',
      primary_status: '504 Gateway Timeout (Simulated)',
      primary_detail: 'Upstream primary provider timed out (>3000ms), tripping circuit breaker threshold',
      failover_model: 'Disaster Recovery Local Fallback (Mock Pool)', failover_status: '200 OK',
      switch_note: 'Hot-swapped to backup pool seamlessly; zero user-facing downtime' },
    { scenario: 'rate-limit', event: 'RATE_LIMIT_SHIFT_TRIGGERED',
      primary_status: '429 Too Many Requests (Simulated)',
      primary_detail: 'Upstream rate limiter triggered (token bucket exhausted), cooldown initiated',
      failover_model: 'Secondary Cluster · Low-Latency Pool', failover_status: '200 OK',
      switch_note: 'Traffic redirected to secondary pool per routing weights' },
    { scenario: 'quality-degrade', event: 'QUALITY_DEGRADE_TRIGGERED',
      primary_status: '200 OK but quality score < 0.6 (Simulated)',
      primary_detail: 'Primary output quality score degraded below acceptable threshold',
      failover_model: 'Secondary Cluster · Regenerated Instance', failover_status: '200 OK (regenerated)',
      switch_note: 'Silently regenerated and verified quality before delivery' }
  ];
  var _failoverIdx = 0;

  function localFailover() {
    var t0 = performance.now();
    var isEn = isLangEn();
    var pool = isEn ? FAILOVER_SCENARIOS_EN : FAILOVER_SCENARIOS;
    var scen = pool[_failoverIdx % pool.length];
    _failoverIdx += 1;
    return Promise.resolve({
      event: scen.event,
      scenario: scen.scenario,
      simulated: true,
      primary_model: isEn ? 'Primary Upstream Cluster (Simulated)' : '上游主模型（仿真占位）',
      primary_status: scen.primary_status,
      primary_detail: scen.primary_detail,
      failover_model: scen.failover_model,
      failover_status: scen.failover_status,
      switch_latency_ms: Math.max(40, Math.round(performance.now() - t0)),
      token_usage: { prompt: 120, completion: 310, cost_usd: 0.00045 },
      token_usage_note: isEn ? 'Sample token usage metric, non-billing' : '样例数值，非真实计费',
      log_entry: isEn ? ('[FAILOVER-ALERT] ' + scen.primary_detail + ', ' + scen.switch_note + '!') : ('[FAILOVER-ALERT] ' + scen.primary_detail + '，' + scen.switch_note + '！')
    });
  }

  /* ---------- 事件总线：真实 SSE 优先，失败降级为示例事件 ---------- */

  // 仅在拿不到后端时使用。界面上会明确标成「示例事件流 · 无后端」，
  // 不会伪装成实时流。
  var SAMPLE_EVENTS = [
    { tag: 'MASTER', level: 'info', msg: 'OmniAgent Platform 统一控制总线初始化完成。' },
    { tag: 'GATEWAY', level: 'info', msg: '流量总线接管，监听 127.0.0.1:8000。' },
    { tag: 'ECOM-AGENT', level: 'info', msg: '珠宝导购 LangGraph 状态机就绪，知识库向量切片预热。' },
    { tag: 'MARKETING', level: 'warn', msg: 'Coze 工作流降级保护加载完成，违禁词库 ' + BANNED_WORDS_DB.length + ' 词。' },
    { tag: 'ANALYTICS', level: 'info', msg: 'DuckDB 内存引擎就绪，挂载电商交易数据集 2,450 笔。' },
    { tag: 'HEALTH', level: 'ok', msg: '全局微服务健康巡检完成，核心业务全部响应。' }
  ];

  var SAMPLE_EVENTS_EN = [
    { tag: 'MASTER', level: 'info', msg: 'OmniAgent Platform unified control bus initialized.' },
    { tag: 'GATEWAY', level: 'info', msg: 'Traffic bus active, listening on 127.0.0.1:8000.' },
    { tag: 'ECOM-AGENT', level: 'info', msg: 'Jewelry Concierge LangGraph state machine ready; vector slices pre-warmed.' },
    { tag: 'MARKETING', level: 'warn', msg: 'Coze workflow fallback protection loaded; compliance database ready.' },
    { tag: 'ANALYTICS', level: 'info', msg: 'DuckDB in-memory OLAP ready; indexed 2,450 transactions.' },
    { tag: 'HEALTH', level: 'ok', msg: 'Global microservice health check passed; all systems operational.' }
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
        var pool = isLangEn() ? SAMPLE_EVENTS_EN : SAMPLE_EVENTS;
        var raw = pool[i % pool.length];
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

  function localXhsGenerate(req) {
    var t0 = performance.now();
    var isEn = isLangEn();
    var rawPname = ((req && req.product_name) || '').trim();
    var pname = rawPname || (isEn ? 'Natural Hetian Nephrite Jade Amulet' : '天然和田碧玉平安扣吊坠');
    if (isEn && (pname === '天然冰种和田碧玉平安扣吊坠' || pname === '天然和田碧玉平安扣吊坠')) {
      pname = 'Natural Hetian Nephrite Jade Amulet';
    }
    var tone = (req && req.tone) || (isEn ? '闺蜜真实种草' : '闺蜜真实种草');
    var rawKw = ((req && req.keywords) || '').trim();
    var kw = rawKw || (isEn ? 'Untreated old-mine rough, lustrous oily sheen, serialized gem certificate, quiet luxury' : '温润细腻, 原矿老料, 权威证书, 新中式穿搭');
    if (isEn && (kw.indexOf('温润细腻') >= 0)) {
      kw = 'Untreated old-mine rough, lustrous oily sheen, serialized gem certificate, quiet luxury';
    }

    var title, hook, content, wechatContent, videoShots, channels, visualPrompts, nodes;

    if (isEn) {
      if (tone.indexOf('避坑') >= 0 || tone.indexOf('guide') >= 0 || tone.indexOf('Guide') >= 0) {
        title = 'The Truth Jewelers Won’t Tell You! 3 Traps to Avoid with [' + pname + '] 💣';
        hook = 'Many assume jade is intimidating. Master these 3 rules, and you can shop like a veteran connoisseur!';
      } else if (tone.indexOf('评测') >= 0 || tone.indexOf('review') >= 0 || tone.indexOf('Expert') >= 0) {
        title = 'Hardcore Teardown: Can You Buy Real Old-Mine [' + pname + '] Under $1,000? Macro Lab Report 🔍';
        hook = 'Armed with a micrometer, UV 365nm torch, and hydrostatic density balance, let’s deconstruct true benchmark old-mine jadeite.';
      } else {
        title = 'Absolute Obsession! The Story Behind Our Signature [' + pname + '] ✨';
        hook = 'Obsessed! Nothing compares to the subtle, lustrous elegance of natural Hetian jade against warm skin tones, zero filter needed!';
      }

      content = hook + '\n\n' +
        'The most frequent DM question this week is about our signature [' + pname + ']. Here is our honest field review and macro breakdown:\n\n' +
        '🌿 Material & Craftsmanship:\n' +
        'Sculpted from untreated old-mine rough, radiating an organic oily luster under sunlight. Hand-polished on both sides for featherlight breathability. Pairs effortlessly with French silk blouses or modern minimalist evening wear!\n\n' +
        '💎 Authenticity & Certification:\n' +
        'Individually serialized with nationally recognized gemological certification. Lifetime re-inspection guaranteed. 100% natural, untreated, and acid-free.\n\n' +
        '🎯 Key Value Highlights:\n' +
        '· Signature Points: ' + kw + '\n' +
        '· Occasions: Everyday quiet luxury, anniversary keepsake, curated self-reward\n\n';

      wechatContent = '[Introduction]\nClients often ask: with an investment mindset, which piece delivers both cultural soul and everyday versatility? My answer is always: a classic amulet sculpted from old-mine natural jade.\n\n1. Appreciating Old-Mine Texture\n[' + pname + '] is selected from untreated natural roughs. It reflects an organic luster rather than artificial glare—quietly capturing depth that only geological time can forge.\n\n2. Styling Versatility\nWhether framing a crisp work shirt or minimalist formal wear, a solitary jade amulet subtly elevates your presence with effortless composure.\n\n3. Guarantee of Authenticity\nEvery piece includes certified lab identification and lifetime verification. An heirloom crafted to accompany life journeys.';

      videoShots = [
        { num: 'Shot 01', type: '[Macro Closeup]', time: '0-3s', visual: '45-degree angle beam on ' + pname + ', showing oily gelatinous translucency as camera pushes in slowly.', audio: '(Hook) "Stop wasting budget on bleached resin! True jade lovers only look for this oily, old-mine glow…"', sfx: 'Crisp jade chime ring' },
        { num: 'Shot 02', type: '[Comparison Med]', time: '3-10s', visual: 'Side-by-side comparison: left hand market-dyed imitation, right hand certified natural jade with embossed hologram cert.', audio: '"Avoid synthetic imitations. Always verify serialized laboratory certificates with lifetime authenticity guarantee!"', sfx: 'Official seal stamp SFX' },
        { num: 'Shot 03', type: '[Model Wearing]', time: '10-22s', visual: 'Model collarbone closeup wearing natural linen blouse, slow-motion natural daylight tracking.', audio: '"Flattering on every skin tone and occasion. Elegant for daily office wear and captivating at formal galas."', sfx: 'Warm ambient lo-fi strings' },
        { num: 'Shot 04', type: '[CTA Closeup]', time: '22-30s', visual: 'Luxury velvet presentation box with polishing cloth and serialized cert. In-feed shopping tag highlighted.', audio: '"Exclusive atelier drop: only 20 pieces curated for this showcase. Tap the shopping tag below to claim yours!"', sfx: 'Countdown heartbeat, cart ping' }
      ];

      channels = {
        xhs: {
          cover_headline: "The Connoisseur's Choice: " + pname,
          title: title,
          content: content,
          tags: ['FineJewelry', 'QuietLuxury', 'NaturalJade', 'DailyWear', pname.replace(/\s+/g, '')]
        },
        wechat: {
          title: "Why True Connoisseurs Quietly Choose " + pname,
          author: 'Qionghua Fine Jewelry',
          quote: '"The beauty of jade reflects virtue—subtle and timeless, transcending transient trends."',
          content: wechatContent,
          stats: { reads: '100k+', wow: '890', likes: '1.2k' }
        },
        video: {
          title: '[Viral Video Script] 30s Master Guide to ' + pname,
          meta: 'Est. 30s · Golden 3-sec Hook · Audio: Modern Lo-fi Strings',
          shots: videoShots
        }
      };

      visualPrompts = [
        'Cover Concept: Soft window daylight, macro close-up of jade pendant resting on raw linen texture with bold luxury serif typography',
        'Frame 2: 45-degree angle beam macro revealing flawless oily gelatinous translucency and zero synthetic resin inclusions',
        'Frame 3: Model styled in Parisian raw silk collar blouse, highlighting collarbone silhouette and gentle drape',
        'Frame 4: Macro close-up of serialized gemological lab certificate with embossed QR code and holographic seal'
      ];

      nodes = [
        { node: 'topic_miner', name: 'Topic Miner Subgraph', status: 'completed', latency_ms: 32, desc: 'Extract high-converting search trends & customer queries' },
        { node: 'hitl_interrupt', name: 'Human-in-the-Loop Interrupt (HITL)', status: 'approved', latency_ms: 15, desc: 'Merchandiser validates strategy and approves pipeline' },
        { node: 'article_writer', name: 'Copywriter Subgraph', status: 'completed', latency_ms: 86, desc: '3-tier emotional storytelling structure with luxury typography' },
        { node: 'visual_prompt', name: 'AI Visual Prompt Director', status: 'completed', latency_ms: 41, desc: 'Generates high-CTR cover hooks and macro shooting directives' },
        { node: 'checkpointer', name: 'Postgres State Checkpointer', status: 'completed', latency_ms: 18, desc: 'Snapshots state history with zero-knowledge PII sanitization' }
      ];
    } else {
      if (tone.indexOf('避坑') >= 0 || tone.indexOf('科普') >= 0) {
        title = '珠宝店员工打死不说的实话！买【' + pname + '】千万别踩这3个雷💣';
        hook = '很多人以为玉石水深，其实只要看懂这三点，新手也能闭眼入！';
      } else if (tone.indexOf('评测') >= 0 || tone.indexOf('专业') >= 0) {
        title = '硬核拆解！千元内能买到真正老坑【' + pname + '】吗？微距实测报告🔍';
        hook = '今天拿卡尺、强光手电和密度计，带大家微距解构一条真正标杆级老坑料。';
      } else {
        title = '一眼沦陷！被闺蜜连环追问链接的【' + pname + '】到底有多绝✨';
        hook = '救命！真的没有人能拒绝天然玉石温润内敛的高级感吧，冷白皮拉满！';
      }

      content = hook + '\n\n' +
        '最近私信问得最多的就是这款【' + pname + '】，今天把实测感受和细节全部分享给大家：\n\n' +
        '🌿 选料与工艺：\n' +
        '精选原矿老坑料子，日光下泛着通透温润的油脂光泽。手工双面精抛光，佩戴在锁骨处极具呼吸感，不管是搭法式通勤衬衫还是新中式新茶服都温婉典雅！\n\n' +
        '💎 品质与证书保障：\n' +
        '一物一证，附带国家级宝玉石质检证书，支持全国权威机构终身复检。无胶无酸洗，佩戴更安心。\n\n' +
        '🎯 核心亮点提炼：\n' +
        '· 核心卖点：' + kw + '\n' +
        '· 适用场景：日常通勤轻奢、闺蜜纪念日送礼、自我犒赏\n\n';

      wechatContent = '【导语】\n很多朋友私信问我，预算有限的前提下，想要一件既有东方气韵又耐看百搭的珠宝，到底该选什么？我的答案始终如一：选一块老坑天然玉料制作的经典平安扣。\n\n一、辨料之妙：什么是真正的“老坑温润”？\n【' + pname + '】精选新疆原矿老料，日光下泛着油脂般内敛的光泽。它不靠火彩夺目，而靠时间沉淀出的水润肌理。手工双面精抛，贴近肌肤处温润如凝脂。\n\n二、搭配之道：新中式美学的画龙点睛\n无论是搭法式通勤衬衫的随性利落，还是新中式茶服的清冷淡雅，一枚平安扣在锁骨之间，恰到好处地点亮了整个人的温婉气场。\n\n三、品质承诺：一物一证，假一赔十\n每一件均附带国家级珠宝玉石质检证书，支持全国权威机构复检。岁月赠礼，长久相伴。';

      videoShots = [
        { num: '分镜 01', type: '【大特写】', time: '0-3s', visual: '45度角强光微距照射' + pname + '，展示透光油脂感与胶质感，镜头慢速推入。', audio: '（情绪抓人）“姐妹们，别再花冤枉钱买酸洗注胶了！真正懂玉的行家，只看这一抹老料油脂光…”', sfx: '清脆玉石轻叩声' },
        { num: '分镜 02', type: '【对比中景】', time: '3-10s', visual: '主播双手对比：左手市场普通染色料，右手且末老矿天然A料，展示证书防伪钢印与一石一码。', audio: '“很多人以为玉石水深，其实认准一石一证一码，全国终身复检，假一赔十！”', sfx: '权威证书盖章音效' },
        { num: '分镜 03', type: '【近景上身】', time: '10-22s', visual: '模特佩戴在锁骨处，搭配白色棉麻新中式上衣，窗边自然光慢动作展示。', audio: '“不挑肤色不挑年龄，戴在颈间是说不出的温润高级。不管是日常通勤还是见长辈，贵气由内而外。”', sfx: '舒缓新中式国风背景音乐' },
        { num: '分镜 04', type: '【促单特写】', time: '22-30s', visual: '精装国风锦盒包装展示，附赠擦玉布与证书，左下角购物车手势指引。', audio: '“今天专场特惠仅放20条，抢完立即下架。点击左下角小黄车，直接结缘带回家！”', sfx: '倒计时心跳声，上链接提示音' }
      ];

      channels = {
        xhs: {
          cover_headline: '真正懂玉的女人，都在悄悄戴【' + pname + '】',
          title: title,
          content: content,
          tags: ['我的首饰分享', '好物推荐', '新中式穿搭', '天然玉石', pname]
        },
        wechat: {
          title: '真正懂玉的女人，都在悄悄佩戴【' + pname + '】',
          author: '琼华东方美学',
          quote: '「玉之美，有如君子之德；温润内敛，胜过一切繁复堆叠。」',
          content: wechatContent,
          stats: { reads: '10万+', wow: '890', likes: '1.2k' }
        },
        video: {
          title: '【爆款短视频带货分镜】30秒讲透' + pname,
          meta: '预期时长: 30s · 节奏: 黄金3秒留人 · BGM: 新中式清冷琵琶',
          shots: videoShots
        }
      };

      visualPrompts = [
        '首图方案：自然窗边柔光拍摄，手持平安扣特写，背景搭配淡青色茶席，打大字标语',
        '图2：强光手电45度角打灯微距，展示内部细腻无杂质的胶质感',
        '图3：新中式棉麻衬衫佩戴全身效果，展示锁骨与颈部线条',
        '图4：国家级权威珠宝质检证书特写与钢印防伪码'
      ];

      nodes = [
        { node: 'topic_miner', name: '爆款选题子图', status: 'completed', latency_ms: 32, desc: '提取小红书大盘热搜词与用户痛点' },
        { node: 'hitl_interrupt', name: '人在环路中断 (HITL)', status: 'approved', latency_ms: 15, desc: '运营人员确认选题大纲并批准流转' },
        { node: 'article_writer', name: '深度成文子图', status: 'completed', latency_ms: 86, desc: '三段式情绪爆款结构与 Emoji 排版' },
        { node: 'visual_prompt', name: 'AI视觉排版方案', status: 'completed', latency_ms: 41, desc: '生成首图高点击封面标语与多图脚本建议' },
        { node: 'checkpointer', name: 'Postgres快照持久化', status: 'completed', latency_ms: 18, desc: '状态持久化落库与 PII 敏感信息脱敏校验' }
      ];
    }

    return Promise.resolve({
      status: 'ok',
      thread_id: 'xhs_langgraph_' + Date.now().toString().slice(-6),
      checkpoint_status: 'persisted_in_postgres',
      title: title,
      content: content,
      tags: isEn ? ['FineJewelry', 'QuietLuxury', 'NaturalJade', 'DailyWear', pname.replace(/\s+/g, '')] : ['我的首饰分享', '新中式穿搭', '天然玉石', '小红书爆款', pname],
      cover_headline: isEn ? ("The Connoisseur's Choice: " + pname) : ('真正懂玉的女人，都在悄悄戴【' + pname + '】'),
      channels: channels,
      visual_prompts: visualPrompts,
      pii_safe: true,
      nodes: nodes,
      latency_ms: Math.round(performance.now() - t0)
    });
  }

  function localFunclipSlice(req) {
    var t0 = performance.now();
    var isEn = isLangEn();
    var sampleId = (req && req.sample_id) || 'sample-1';
    var hotwords = (req && req.hotwords) || (isEn ? 'Imperial Green, Translucent, Grade-A, Untreated, Hetian Jade' : '冰种, 玻璃种, 帝王绿, 极品阳绿, 缅甸老坑, 和田碧玉');

    var sampleTitle, durationStr, clips, dialogue, srtContent;

    if (isEn) {
      if (sampleId === 'sample-2') {
        sampleTitle = '[Expert Appraisal] Burmese Old-Mine Jadeite: Identifying Bleaching vs. Natural Fluorescence';
        durationStr = '01:18:45';
        clips = [
          { id: 1, title: 'Natural Gel Texture vs. Acid Resin Bleaching Indicators', start: '00:04:12', end: '00:05:30', duration: '01:18', confidence: 0.988, hotwords: ['Jadeite', 'Natural Glow', 'Old-Mine'] },
          { id: 2, title: 'Ultraviolet 365nm Lamp Fluorescence Verification', start: '00:12:05', end: '00:13:40', duration: '01:35', confidence: 0.992, hotwords: ['UV Reaction', 'Grade-A Jade'] },
          { id: 3, title: 'National Laboratory Serialized Seal Verification Flow', start: '00:25:30', end: '00:26:45', duration: '01:15', confidence: 0.985, hotwords: ['Serialized Cert', 'Lab Verified'] }
        ];
        dialogue = [
          { time: '00:04:12.300 -> 00:04:20.100', speaker: 'Spk 1 (Senior Appraiser)', text: 'Observe the subdued oily luster under natural daylight. True old-mine gelatinous glow is restrained and organic.' },
          { time: '00:04:20.500 -> 00:04:28.400', speaker: 'Spk 2 (Collector)', text: 'What is the most telling sign under 365nm UV light for treated or polymer-injected bangles?' },
          { time: '00:04:28.800 -> 00:04:36.900', speaker: 'Spk 1 (Senior Appraiser)', text: 'Polymer epoxy fluoresces bright chalky blue along structural fractures, whereas untreated Grade-A remains completely inert.' }
        ];
        srtContent = '1\n00:04:12,300 --> 00:04:20,100\n[Spk 1] Observe the subdued oily luster under natural daylight. True old-mine gelatinous glow is restrained and organic.\n\n2\n00:04:20,500 --> 00:04:28,400\n[Spk 2] What is the most telling sign under 365nm UV light for treated or polymer-injected bangles?\n\n3\n00:04:28,800 --> 00:04:36,900\n[Spk 1] Polymer epoxy fluoresces bright chalky blue along structural fractures, whereas untreated Grade-A remains completely inert.';
      } else if (sampleId === 'sample-3') {
        sampleTitle = '[Atelier Macro] Heritage Gold Wire Inlay on Hetian Jade Masterclass';
        durationStr = '00:54:20';
        clips = [
          { id: 1, title: '0.1mm Ultra-Fine 24K Gold Wire Manual Groove Embedding', start: '00:02:10', end: '00:03:35', duration: '01:25', confidence: 0.986, hotwords: ['Gold Inlay', 'Master Heritage'] },
          { id: 2, title: 'Nephrite Polishing and Harmonious Gold-Jade Lustrous Finish', start: '00:15:20', end: '00:16:45', duration: '01:25', confidence: 0.995, hotwords: ['Hetian Jade', 'Gold & Jade'] },
          { id: 3, title: 'Master Craftsman on Ancient Palace Inlay Preservation', start: '00:31:00', end: '00:32:15', duration: '01:15', confidence: 0.978, hotwords: ['Palace Craft', 'Imperial Inlay'] }
        ];
        dialogue = [
          { time: '00:02:10.150 -> 00:02:18.400', speaker: 'Spk 1 (Master Artisan)', text: 'Embedding the pure gold filament requires continuous pressure in a single breath; uneven force risks cracking the jade base.' },
          { time: '00:02:18.800 -> 00:02:26.500', speaker: 'Spk 2 (Documentary Host)', text: 'This batch utilizes untreated Qiemo green nephrite, harmonizing with 24K gold to symbolize enduring fortune.' }
        ];
        srtContent = '1\n00:02:10,150 --> 00:02:18,400\n[Spk 1] Embedding the pure gold filament requires continuous pressure in a single breath; uneven force risks cracking the jade base.\n\n2\n00:02:18,800 --> 00:02:26,500\n[Spk 2] This batch utilizes untreated Qiemo green nephrite, harmonizing with 24K gold to symbolize enduring fortune.';
      } else {
        sampleTitle = '[Live Highlight] 3-Hour Gemstone Live Auction & Raw Stone Bidding';
        durationStr = '03:12:48';
        clips = [
          { id: 1, title: 'Raw Rough Sliced: Imperial Vivid Green Revealed', start: '00:00:15', end: '00:01:42', duration: '01:27', confidence: 0.994, hotwords: ['Imperial Green', 'Grade-A Rough'] },
          { id: 2, title: 'High-Stakes Live Price Negotiation & Deal Locked', start: '00:03:10', end: '00:04:25', duration: '01:15', confidence: 0.989, hotwords: ['Direct Source', 'Collector Drop'] },
          { id: 3, title: 'National Laboratory Serialized Certificate Showcase', start: '00:07:05', end: '00:08:18', duration: '01:13', confidence: 0.981, hotwords: ['Lab Certificate', 'QR Verification'] }
        ];
        dialogue = [
          { time: '00:00:15.240 -> 00:00:23.810', speaker: 'Spk 1 (Lead Host)', text: 'Look at the light penetration! Intense fluorescence throughout; the entire rough has melted into top-tier Imperial Green!' },
          { time: '00:00:24.100 -> 00:00:31.500', speaker: 'Spk 2 (Co-Host)', text: 'Type 1 in chat to reserve right now! Only one piece carved from this boulder, all middlemen fees completely cut!' },
          { time: '00:00:31.900 -> 00:00:39.400', speaker: 'Spk 1 (Lead Host)', text: 'Accompanied by national laboratory certificate, lifetime verification, 10x guarantee. 3, 2, 1, link is live!' }
        ];
        srtContent = '1\n00:00:15,240 --> 00:00:23,810\n[Spk 1] Look at the light penetration! Intense fluorescence throughout; the entire rough has melted into top-tier Imperial Green!\n\n2\n00:00:24,100 --> 00:00:31,500\n[Spk 2] Type 1 in chat to reserve right now! Only one piece carved from this boulder, all middlemen fees completely cut!\n\n3\n00:00:31,900 --> 00:00:39,400\n[Spk 1] Accompanied by national laboratory certificate, lifetime verification, 10x guarantee. 3, 2, 1, link is live!';
      }
    } else {
      if (sampleId === 'sample-2') {
        sampleTitle = '【专业鉴宝】缅甸老坑冰种辨伪与荧光起胶实物解说';
        durationStr = '01:18:45';
        clips = [
          { id: 1, title: '老坑料起胶与注胶酸洗鉴别要点', start: '00:04:12', end: '00:05:30', duration: '01:18', confidence: 0.988, hotwords: ['冰种', '起胶', '老坑'] },
          { id: 2, title: '紫外荧光灯下荧光反应实测对比', start: '00:12:05', end: '00:13:40', duration: '01:35', confidence: 0.992, hotwords: ['荧光反应', '天然A货'] },
          { id: 3, title: '国检证书钢印与防伪查询全流程', start: '00:25:30', end: '00:26:45', duration: '01:15', confidence: 0.985, hotwords: ['一石一证', '质检证书'] }
        ];
        dialogue = [
          { time: '00:04:12.300 -> 00:04:20.100', speaker: 'Spk 1 (鉴宝专家)', text: '注意看这块老坑冰种手镯在自然光下的油脂感，真正的起胶是自然内敛的光晕。' },
          { time: '00:04:20.500 -> 00:04:28.400', speaker: 'Spk 2 (求鉴藏友)', text: '那老师如果用紫光灯照，市面上那种B货和注胶手镯会有什么明显的区别吗？' },
          { time: '00:04:28.800 -> 00:04:36.900', speaker: 'Spk 1 (鉴宝专家)', text: '问到关键了！注胶充填的环氧树脂在365nm波长下会产生强烈的蓝色荧光残留，而天然A货通体纯净。' }
        ];
        srtContent = '1\n00:04:12,300 --> 00:04:20,100\n[Spk 1] 注意看这块老坑冰种手镯在自然光下的油脂感，真正的起胶是自然内敛的光晕。\n\n2\n00:04:20,500 --> 00:04:28,400\n[Spk 2] 那老师如果用紫光灯照，市面上那种B货和注胶手镯会有什么明显的区别吗？\n\n3\n00:04:28,800 --> 00:04:36,900\n[Spk 1] 问到关键了！注胶充填的环氧树脂在365nm波长下会产生强烈的蓝色荧光残留，而天然A货通体纯净。';
      } else if (sampleId === 'sample-3') {
        sampleTitle = '【工艺微距】非遗手工金丝镶嵌和田玉制作工序全记录';
        durationStr = '00:54:20';
        clips = [
          { id: 1, title: '0.1mm极细纯金丝手工压嵌凹槽工序', start: '00:02:10', end: '00:03:35', duration: '01:25', confidence: 0.986, hotwords: ['金丝镶嵌', '非遗手工'] },
          { id: 2, title: '和田碧玉打磨抛光与金玉生辉特写', start: '00:15:20', end: '00:16:45', duration: '01:25', confidence: 0.995, hotwords: ['和田碧玉', '金玉良缘'] },
          { id: 3, title: '匠人解说中国传统宫廷错金银技艺传承', start: '00:31:00', end: '00:32:15', duration: '01:15', confidence: 0.978, hotwords: ['错金银', '宫廷古法'] }
        ];
        dialogue = [
          { time: '00:02:10.150 -> 00:02:18.400', speaker: 'Spk 1 (非遗大师)', text: '压金丝必须一气耗成，力度稍微不均就会伤及玉器底胎，这是手艺人几十年的功夫。' },
          { time: '00:02:18.800 -> 00:02:26.500', speaker: 'Spk 2 (纪录采访)', text: '这块选用的是新疆且末的天然和田碧玉，与纯金搭配有金玉满堂的吉祥寓意。' }
        ];
        srtContent = '1\n00:02:10,150 --> 00:02:18,400\n[Spk 1] 压金丝必须一气耗成，力度稍微不均就会伤及玉器底胎，这是手艺人几十年的功夫。\n\n2\n00:02:18,800 --> 00:02:26,500\n[Spk 2] 这块选用的是新疆且末的天然和田碧玉，与纯金搭配有金玉满堂的吉祥寓意。';
      } else {
        sampleTitle = '【直播高光】3小时珠宝原石砍价开石现场 (主播 vs 货主激情拉扯)';
        durationStr = '03:12:48';
        clips = [
          { id: 1, title: '原石切开爆出极品阳绿高光解说', start: '00:00:15', end: '00:01:42', duration: '01:27', confidence: 0.994, hotwords: ['极品阳绿', '帝王绿', '冰种'] },
          { id: 2, title: '主播与货主封箱砍价极限拉扯', start: '00:03:10', end: '00:04:25', duration: '01:15', confidence: 0.989, hotwords: ['缅甸老坑', '放漏'] },
          { id: 3, title: '一石一卡国检防伪证书展示', start: '00:07:05', end: '00:08:18', duration: '01:13', confidence: 0.981, hotwords: ['国检证书', '一石一证'] }
        ];
        dialogue = [
          { time: '00:00:15.240 -> 00:00:23.810', speaker: 'Spk 1 (主讲主播)', text: '家人们注意看打灯后的表现！荧光非常强，整块老坑料子已经完全化开了，是难得的极品阳绿！' },
          { time: '00:00:24.100 -> 00:00:31.500', speaker: 'Spk 2 (带货助播)', text: '公屏扣 1 的粉丝直接锁单，今天只有这一块老坑料，中间商差价全部砍到底！' },
          { time: '00:00:31.900 -> 00:00:39.400', speaker: 'Spk 1 (主讲主播)', text: '附带国家级质检证书，支持全国终身复检，假一赔十！3、2、1，直接上链接！' }
        ];
        srtContent = '1\n00:00:15,240 --> 00:00:23,810\n[Spk 1] 家人们注意看打灯后的表现！荧光非常强，整块老坑料子已经完全化开了，是难得的极品阳绿！\n\n2\n00:00:24,100 --> 00:00:31,500\n[Spk 2] 公屏扣 1 的粉丝直接锁单，今天只有这一块老坑料，中间商差价全部砍到底！\n\n3\n00:00:31,900 --> 00:00:39,400\n[Spk 1] 附带国家级质检证书，支持全国终身复检，假一赔十！3、2、1，直接上链接！';
      }
    }

    return Promise.resolve({
      status: 'ok',
      sample_id: sampleId,
      sample_title: sampleTitle,
      duration: durationStr,
      hotwords_hit: hotwords.split(',').map(function (w) { return w.trim(); }).filter(Boolean).slice(0, 5),
      speech_engine: isEn ? 'FunASR Paraformer Offline (Industrial Level)' : 'FunASR Paraformer 离线高精引擎 (工业级)',
      accuracy_rate: '99.2%',
      clips: clips,
      dialogue: dialogue,
      srt_content: srtContent,
      latency_ms: Math.round(performance.now() - t0)
    });
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

    xhsGenerate: function (payload, asyncTask) {
      var isAsync = !!asyncTask;
      var body = typeof payload === 'string' ? { topic: payload } : (payload || {});
      var path = '/api/v1/labs/xhs/generate' + (isAsync ? '?async_task=true' : '');
      return apiCall(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }).catch(function () {
        if (isAsync) {
          return {
            status: 'ok',
            async: true,
            task_id: 'task-offline-' + Math.random().toString(36).substring(2, 9),
            message: '离线演示：异步任务已创建并推入本地模拟状态机'
          };
        }
        return localXhsGenerate(body);
      });
    },

    funclipSlice: function (payload, asyncTask) {
      var isAsync = !!asyncTask;
      var body = typeof payload === 'string' ? { video_name: payload } : (payload || {});
      var path = '/api/v1/labs/funclip/slice' + (isAsync ? '?async_task=true' : '');
      return apiCall(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }).catch(function () {
        if (isAsync) {
          return {
            status: 'ok',
            async: true,
            task_id: 'task-offline-' + Math.random().toString(36).substring(2, 9),
            message: '离线演示：FunClip 视频切片任务已生成'
          };
        }
        return localFunclipSlice(body);
      });
    },

    analysisQuery: function (queryText) {
      return apiCall('/api/v1/analysis/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query_text: queryText })
      }).catch(function () { return localAnalysis({ query_text: queryText }); });
    },

    /** 网关容灾仿真：优先走后端（三场景轮换），静态模式降级为本地仿真。
     *  返回字段两种模式保持一致（scenario/event/primary_status/...）。 */
    gatewayFailover: function () {
      return apiCall('/api/v1/gateway/simulate_failover', { method: 'POST' })
        .catch(function () { return localFailover(); });
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
    },

    /** 全链路 Trace ID 审计流水线。静态模式返回内置样例 Trace，标 sample: true。 */
    fetchTraces: function (limit) {
      var n = limit || 15;
      return apiCall('/api/v1/gateway/traces?limit=' + n, { timeoutMs: 5000 })
        .catch(function () { return sampleTraces(n); });
    },

    /** 统一 OpenAI 规范 Chat Completions 代理调用 */
    openaiChat: function (payload) {
      return apiCall('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).catch(function () { return localOpenaiChat(payload); });
    },

    /** 企业级后台异步任务流水查询 */
    fetchTasks: function (limit) {
      var n = limit || 20;
      return apiCall('/api/v1/tasks?limit=' + n, { timeoutMs: 5000 })
        .catch(function () {
          var tId = (typeof window !== 'undefined' && window.OmniStore && window.OmniStore.get('tenant')) || 'tenant-hq';
          return {
            status: 'ok',
            tenant_id: tId,
            total: 2,
            tasks: [
              {
                id: 'task-sim-8801',
                task_type: 'funclip_slice',
                tenant_id: tId,
                status: 'RUNNING',
                progress: 68.5,
                elapsed_ms: 1240,
                created_at: new Date(Date.now() - 15000).toISOString(),
                payload: { video_name: 'luxury_ring_macro_4k.mp4', time_range: [0.0, 15.0] }
              },
              {
                id: 'task-sim-8802',
                task_type: 'xhs_generate',
                tenant_id: tId,
                status: 'COMPLETED',
                progress: 100.0,
                elapsed_ms: 820,
                created_at: new Date(Date.now() - 60000).toISOString(),
                payload: { topic: 'Moissanite Engagement Ring #7701', channel: 'instagram' }
              }
            ]
          };
        });
    },

    /** 查询特定异步任务状态机进度与执行成果 */
    fetchTaskDetail: function (taskId) {
      return apiCall('/api/v1/tasks/' + encodeURIComponent(taskId), { timeoutMs: 5000 })
        .catch(function () {
          return { status: 'not_found', task: null };
        });
    },

    /** 申请签发企业级 JWT Token */
    requestAuthToken: function (tenantId, role, userId) {
      return apiCall('/api/v1/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tenant_id: tenantId || 'tenant-hq',
          role: role || 'admin',
          user_id: userId || 'usr-default'
        })
      }).catch(function () {
        return {
          status: 'ok',
          access_token: 'mock-jwt-token-offline',
          tenant_id: tenantId,
          role: role
        };
      });
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

  function sampleTraces(limit) {
    var now = new Date();
    var formatTime = function (d) {
      return d.toTimeString().split(' ')[0];
    };
    var traces = [
      {
        trace_id: 'tr-' + Math.floor(Math.random() * 89999 + 10000) + '-ok',
        timestamp: formatTime(now),
        method: 'POST',
        path: '/v1/chat/completions',
        service: 'ai-gateway',
        status_code: 200,
        latency_ms: 38,
        model: 'Qwen-Max',
        tokens: 340
      },
      {
        trace_id: 'tr-' + Math.floor(Math.random() * 89999 + 10000) + '-hit',
        timestamp: formatTime(new Date(now.getTime() - 4000)),
        method: 'POST',
        path: '/api/v1/labs/xhs/generate',
        service: 'content-factory',
        status_code: 200,
        latency_ms: 54,
        model: 'LangGraph-1.0',
        tokens: 580
      },
      {
        trace_id: 'tr-' + Math.floor(Math.random() * 89999 + 10000) + '-asr',
        timestamp: formatTime(new Date(now.getTime() - 9000)),
        method: 'POST',
        path: '/api/v1/labs/funclip/slice',
        service: 'funclip-studio',
        status_code: 200,
        latency_ms: 45,
        model: 'FunASR-Paraformer',
        tokens: 290
      },
      {
        trace_id: 'tr-' + Math.floor(Math.random() * 89999 + 10000) + '-rag',
        timestamp: formatTime(new Date(now.getTime() - 14000)),
        method: 'POST',
        path: '/api/v1/rag/search',
        service: 'rag-retrieval',
        status_code: 200,
        latency_ms: 32,
        model: 'Hybrid-Engine',
        tokens: 180
      },
      {
        trace_id: 'tr-' + Math.floor(Math.random() * 89999 + 10000) + '-mon',
        timestamp: formatTime(new Date(now.getTime() - 20000)),
        method: 'GET',
        path: '/api/v1/overview/stats',
        service: 'core-hub',
        status_code: 200,
        latency_ms: 22,
        model: 'Hybrid-Engine',
        tokens: 95
      }
    ];
    return Promise.resolve({
      status: 'ok',
      source: 'sample',
      traces: traces.slice(0, limit || 5),
      summary: {
        total_recorded: traces.length,
        p95_latency_ms: 42,
        success_rate: 100.0,
        active_protocol: 'OpenAI v1 / Anthropic MCP (Static Simulation)',
        proxy_endpoint: '/v1/chat/completions'
      }
    });
  }

  function localOpenaiChat(payload) {
    var userMsg = '你好';
    if (payload && payload.messages && payload.messages.length > 0) {
      userMsg = payload.messages[payload.messages.length - 1].content || userMsg;
    }
    var trId = 'tr-sim-' + Math.floor(Math.random() * 89999 + 10000);
    return Promise.resolve({
      id: 'chatcmpl-' + trId,
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: (payload && payload.model) || 'qwen-max',
      system_fingerprint: 'fp_local_demo',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: '【OmniAgent 统一模型代理】已通过智能网关调度响应：针对您的问题「' + userMsg + '」，系统已成功完成意图识别与工具编排，链路全程受 Trace ID [' + trId + '] 审计追踪。'
          },
          finish_reason: 'stop'
        }
      ],
      usage: {
        prompt_tokens: userMsg.length * 2 + 35,
        completion_tokens: 160,
        total_tokens: userMsg.length * 2 + 195,
        cost_usd: 0.00039
      },
      trace_id: trId,
      latency_ms: 42,
      proxy_gateway: 'OmniAgent AI Gateway (Static Simulation)'
    });
  }

  window.OmniAPI = OmniAPI;
})();
