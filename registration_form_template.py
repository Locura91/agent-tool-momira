# Auto-generated — edit this file directly; registration_form_template.py IS the source of truth.
TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{PKG_TITLE}} — {{AGENCY_NAME}}</title>
  <style>
    :root{
      --brand:#17a39b;--brand-dark:#128a81;--brand-light:#e6f7f6;
      --ink:#111827;--muted:#6b7280;--border:#e5e7eb;
      --bg:#f5f6f8;--white:#fff;--red:#dc2626;
    }
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      background:var(--bg);color:var(--ink);min-height:100vh}

    /* ── Top bar ── */
    .topbar{background:var(--brand);padding:.4rem 1.2rem;
      display:flex;align-items:center;justify-content:space-between;
      font-size:.72rem;font-weight:700;color:rgba(255,255,255,.9);
      text-transform:uppercase;letter-spacing:.06em}
    .topbar-logo{height:28px;max-width:120px;object-fit:contain;filter:brightness(0) invert(1)}
    .topbar-name{color:#fff;font-size:.72rem;font-weight:700}

    /* ── Hero ── */
    .hero{background:var(--white);border-bottom:1px solid var(--border)}
    .hero-img{width:100%;height:240px;object-fit:cover;display:block}
    .hero-img-placeholder{width:100%;height:200px;
      background:linear-gradient(135deg,var(--brand-light) 0%,var(--brand) 100%);
      display:flex;align-items:center;justify-content:center;font-size:3.5rem}
    .hero-body{padding:1.2rem 1.4rem 1.1rem}
    .hero h1{font-size:1.45rem;font-weight:800;line-height:1.25;
      color:var(--ink);margin-bottom:.6rem}

    .meta-strip{display:flex;flex-wrap:wrap;gap:.4rem .8rem;
      font-size:.8rem;color:var(--muted);margin-bottom:.75rem;align-items:center}
    .meta-strip strong{color:var(--ink)}
    .meta-pill{background:var(--brand-light);color:var(--brand);
      font-weight:700;font-size:.72rem;padding:.2rem .6rem;
      border-radius:20px;white-space:nowrap}

    .route-strip{display:flex;flex-wrap:wrap;align-items:center;
      gap:.25rem .1rem;margin-bottom:.8rem;font-size:.8rem}
    .route-chip{background:#f3f4f6;color:var(--ink);font-weight:600;
      font-size:.74rem;padding:.22rem .6rem;border-radius:20px}
    .route-arrow{color:var(--muted);font-size:.75rem;padding:0 .1rem}

    .dep-row{font-size:.77rem;color:var(--muted);margin-bottom:.8rem;
      display:flex;flex-wrap:wrap;gap:.3rem;align-items:center}
    .dep-chip{background:#fef3c7;color:#92400e;font-weight:700;
      font-size:.72rem;padding:.2rem .6rem;border-radius:20px}

    .price-block{display:flex;align-items:baseline;gap:.35rem;margin-bottom:.7rem}
    .price-from{font-size:.8rem;color:var(--muted)}
    .price-amount{font-size:1.8rem;font-weight:900;color:var(--ink);line-height:1}
    .price-unit{font-size:.8rem;color:var(--muted)}

    .pkg-desc{font-size:.82rem;color:var(--muted);line-height:1.65;
      border-top:1px solid var(--border);padding-top:.8rem;margin-top:.4rem}

    /* ── Page ── */
    .page{max-width:720px;margin:0 auto;padding:1.2rem 1rem 3rem}

    /* ── Section heading ── */
    .section-head{font-size:1rem;font-weight:800;color:var(--ink);
      margin:1.5rem 0 .9rem;padding-bottom:.4rem;
      border-bottom:2px solid var(--brand)}

    /* ── Itinerary timeline ── */
    .timeline{display:flex;flex-direction:column;gap:0}
    .tl-row{display:flex;gap:0;position:relative}
    .tl-row:not(:last-child) .tl-line::after{
      content:'';position:absolute;
      left:50%;top:44px;transform:translateX(-50%);
      width:2px;bottom:-1px;background:var(--border);z-index:0}
    .tl-left{width:52px;flex-shrink:0;display:flex;flex-direction:column;
      align-items:center;padding-top:6px;position:relative}
    .tl-line{position:relative;display:flex;flex-direction:column;align-items:center;width:100%}
    .tl-icon{width:36px;height:36px;border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-size:.95rem;flex-shrink:0;z-index:1;position:relative}
    .icon-flight  {background:#dbeafe;color:#1d4ed8}
    .icon-bus     {background:#e0f2fe;color:#0369a1}
    .icon-ferry   {background:#cffafe;color:#0e7490}
    .icon-train   {background:#dcfce7;color:#166534}
    .icon-car     {background:#fef9c3;color:#854d0e}
    .icon-hotel   {background:#fef3c7;color:#92400e}
    .icon-transfer{background:#d1fae5;color:#065f46}
    .icon-activity{background:#ede9fe;color:#5b21b6}
    .icon-cruise  {background:#e0e7ff;color:#3730a3}
    .tl-date-side{font-size:.58rem;font-weight:700;color:var(--muted);
      text-align:center;margin-top:.25rem;text-transform:uppercase;line-height:1.2}

    .tl-body{flex:1;min-width:0;padding:.2rem 0 1.1rem .85rem}
    .tl-type{font-size:.62rem;font-weight:700;text-transform:uppercase;
      letter-spacing:.06em;color:var(--brand);margin-bottom:.2rem}
    .tl-title{font-size:.92rem;font-weight:700;color:var(--ink);margin-bottom:.2rem}
    .tl-stars{color:#f59e0b;font-size:.78rem;letter-spacing:1px;margin-bottom:.2rem}
    .tl-chips{display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:.25rem}
    .chip{font-size:.67rem;padding:.18rem .5rem;border-radius:4px;font-weight:600}
    .chip-board   {background:#dcfce7;color:#166534}
    .chip-nights  {background:#fef3c7;color:#92400e}
    .chip-luggage {background:#dbeafe;color:#1d4ed8}
    .chip-time    {background:#f3f4f6;color:var(--ink)}
    .chip-dur     {background:#f3f4f6;color:var(--muted)}

    .no-itin{background:var(--white);border:1px solid var(--border);
      border-radius:10px;padding:1rem 1.2rem;font-size:.85rem;color:var(--muted);
      line-height:1.6}

    /* ── Notice ── */
    .notice{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;
      padding:.9rem 1.1rem;margin-bottom:1.2rem;display:flex;gap:.7rem}
    .notice-icon{font-size:1.2rem;flex-shrink:0}
    .notice-title{font-weight:700;font-size:.85rem;margin-bottom:.2rem}
    .notice p{font-size:.79rem;color:#78350f;line-height:1.5}

    /* ── Form card ── */
    .form-card{background:var(--white);border:1px solid var(--border);
      border-radius:12px;margin-bottom:1.1rem;overflow:hidden;
      box-shadow:0 1px 4px rgba(0,0,0,.05)}
    .pax-header{background:var(--brand-light);padding:.7rem 1.2rem;
      font-size:.72rem;font-weight:700;text-transform:uppercase;
      letter-spacing:.06em;color:var(--brand)}
    .pax-body{padding:1rem 1.2rem}
    .field{display:flex;flex-direction:column;gap:.25rem;margin-bottom:.65rem}
    .field:last-child{margin-bottom:0}
    label.fl{font-size:.77rem;font-weight:600}
    label.fl .req{color:var(--red)}
    select,input[type=text],input[type=email],input[type=tel],input[type=date]{
      width:100%;padding:.55rem .75rem;
      border:1.5px solid var(--border);border-radius:8px;
      font-size:.88rem;color:var(--ink);background:var(--white);
      outline:none;transition:border-color .15s;-webkit-appearance:none;
      appearance:none}
    select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%236b7280' d='M6 8L0 0h12z'/%3E%3C/svg%3E");
      background-repeat:no-repeat;background-position:right .75rem center;
      padding-right:2rem}
    input:focus,select:focus{border-color:var(--brand)}
    input.err,select.err{border-color:var(--red)}
    .ferr{font-size:.72rem;color:var(--red);display:none}
    .ferr.show{display:block}
    .row3{display:grid;grid-template-columns:100px 1fr 1fr;gap:.5rem}
    .row2{display:grid;grid-template-columns:1fr 90px;gap:.5rem}
    .row2b{display:grid;grid-template-columns:110px 1fr;gap:.5rem}
    .divider{border:none;border-top:1px solid var(--border);margin:.6rem 0}

    /* ── T&C ── */
    .tc-body{padding:1rem 1.2rem}
    .tc-item{display:flex;gap:.65rem;align-items:flex-start;margin-bottom:.7rem}
    .tc-item:last-child{margin-bottom:0}
    .tc-item input[type=checkbox]{width:17px;height:17px;flex-shrink:0;
      accent-color:var(--brand);margin-top:.15rem;cursor:pointer}
    .tc-item label{font-size:.8rem;line-height:1.55;cursor:pointer}
    .tc-item label a{color:var(--brand)}
    .tc-err{font-size:.72rem;color:var(--red);display:none;margin-top:.2rem}
    .tc-err.show{display:block}

    /* ── Submit ── */
    .submit-wrap{padding:1rem 1.2rem;background:var(--bg);border-top:1px solid var(--border)}
    .btn-submit{width:100%;background:var(--brand);color:#fff;border:none;
      border-radius:10px;padding:.8rem 1.5rem;font-size:1rem;font-weight:700;
      cursor:pointer;transition:background .15s}
    .btn-submit:hover{background:var(--brand-dark)}
    .btn-submit:disabled{opacity:.6;cursor:not-allowed}
    .submit-note{text-align:center;font-size:.74rem;color:var(--muted);
      margin-top:.5rem;line-height:1.5}
    .err-banner{background:#fef2f2;border:1px solid #fca5a5;color:var(--red);
      border-radius:8px;padding:.6rem 1rem;font-size:.84rem;
      margin-bottom:1rem;display:none}
    .err-banner.show{display:block}

    @media(max-width:480px){
      .row3{grid-template-columns:1fr 1fr}
      .row3>:first-child{grid-column:1/-1}
      .row2,.row2b{grid-template-columns:1fr}
    }
  </style>
</head>
<body>

<div class="topbar">
  {{LOGO_HTML}}
  <span class="topbar-name">{{AGENCY_NAME}}</span>
</div>

<div class="hero">
  {{HERO_IMG_HTML}}
  <div class="hero-body">
    <h1>{{PKG_TITLE}}</h1>

    <div class="meta-strip" id="meta-strip">
      <span id="meta-duration"></span>
      <span id="meta-travelers"></span>
    </div>

    <div class="route-strip" id="route-row">{{ROUTE_HTML}}</div>

    <div class="dep-row" id="dep-row">{{DEPARTURES_HTML}}</div>

    <div class="price-block" id="price-block">
      <span class="price-from">from</span>
      <span class="price-amount">{{PRICE_STR}}</span>
      <span class="price-unit">/ person</span>
    </div>

    <div class="pkg-desc" id="pkg-desc">{{PKG_DESC}}</div>
  </div>
</div>

<div class="page">

  <!-- Itinerary -->
  <div class="section-head">Trip Itinerary</div>
  <div class="timeline" id="timeline">
    <div style="color:var(--muted);font-size:.85rem;padding:.5rem 0">Loading…</div>
  </div>

  <!-- Reservation notice -->
  <div class="notice" style="margin-top:1.5rem">
    <span class="notice-icon">ℹ️</span>
    <div>
      <div class="notice-title">Reservation request — not a confirmed booking</div>
      <p>By submitting this form you are placing a <strong>reservation request</strong>.
         Your travel agent at <strong>{{AGENCY_NAME}}</strong> will contact you directly
         to confirm availability and price. No booking is made until you receive written confirmation.</p>
    </div>
  </div>

  <div class="err-banner" id="err-banner"></div>

  <form id="reg-form" method="post"
        action="/register/{{AGENT_ID}}/{{PACKAGE_ID}}" novalidate>

    <div class="section-head">Traveler Details</div>
    <div id="pax-sections"></div>

    <div class="section-head">Contact Details</div>
    <div class="form-card">
      <div class="pax-body">
        <div class="field">
          <label class="fl" for="f-email">E-mail <span class="req">*</span></label>
          <input type="email" id="f-email" name="email" autocomplete="email"
                 placeholder="name@example.com" required>
          <span class="ferr" id="e-email">Please enter a valid email address.</span>
        </div>
        <div class="field">
          <label class="fl" for="f-phone">Phone <span class="req">*</span></label>
          <input type="tel" id="f-phone" name="phone" autocomplete="tel"
                 placeholder="+49" required>
          <span class="ferr" id="e-phone">Please enter a phone number.</span>
        </div>
        <hr class="divider">
        <div class="field">
          <label class="fl">Country of residence <span class="req">*</span></label>
          <input type="text" id="f-country" name="country_of_residence"
                 placeholder="e.g. Germany" autocomplete="country-name" required>
          <span class="ferr" id="e-country">Please enter your country.</span>
        </div>
        <div class="field">
          <label class="fl">Postal code &amp; city <span class="req">*</span></label>
          <div class="row2b">
            <input type="text" id="f-postal" name="postal_code" placeholder="Postal code" required>
            <input type="text" id="f-city" name="city" placeholder="City" required>
          </div>
          <span class="ferr" id="e-city">Please enter postal code and city.</span>
        </div>
        <div class="field">
          <label class="fl">Street &amp; house number <span class="req">*</span></label>
          <div class="row2">
            <input type="text" id="f-street" name="street" placeholder="Street name" required>
            <input type="text" id="f-house" name="house_number" placeholder="No.">
          </div>
          <span class="ferr" id="e-street">Please enter a street.</span>
        </div>
      </div>
    </div>

    <div class="section-head">Terms &amp; Conditions</div>
    <div class="form-card">
      <div class="tc-body">
        <div class="tc-item">
          <input type="checkbox" id="tc-reservation" name="tc_reservation">
          <label for="tc-reservation">
            I understand this is a <strong>reservation request only</strong>, not a confirmed booking.
            My travel agent will contact me to confirm availability and price.
            I will not be charged until I receive written booking confirmation.
          </label>
        </div>
        <span class="tc-err" id="e-tc-reservation">Please confirm you understand this is a reservation.</span>

        <div class="tc-item">
          <input type="checkbox" id="tc-terms" name="tc_terms">
          <label for="tc-terms">
            I have read and accept the
            <a href="https://momira.travel/terms" target="_blank" rel="noopener">General Terms &amp; Conditions of Momira Travel</a>,
            including the cancellation and payment policies.
          </label>
        </div>
        <span class="tc-err" id="e-tc-terms">Please accept the Terms &amp; Conditions.</span>

        <div class="tc-item">
          <input type="checkbox" id="tc-data" name="tc_data">
          <label for="tc-data">
            I agree that my personal data will be processed solely for this travel reservation
            in accordance with applicable data protection law (GDPR).
          </label>
        </div>
        <span class="tc-err" id="e-tc-data">Please accept the data protection clause.</span>

        <div class="tc-item">
          <input type="checkbox" id="tc-accuracy" name="tc_accuracy">
          <label for="tc-accuracy">
            I confirm all passenger details are accurate and match the official travel documents (passport / ID).
          </label>
        </div>
        <span class="tc-err" id="e-tc-accuracy">Please confirm the details are accurate.</span>
      </div>

      <div class="submit-wrap">
        <button type="submit" class="btn-submit" id="submit-btn">
          ✈️ Submit reservation request
        </button>
        <div class="submit-note">
          By submitting you confirm all details are accurate and accept the terms above.<br>
          Your travel agent will contact you as soon as possible to confirm your booking.
        </div>
      </div>
    </div>

    <input type="hidden" name="passengers_json" id="passengers-json">
  </form>
</div>

<script type="application/json" id="itin-data">{{ITINERARY_JSON}}</script>
<script>
  const NUM_ADULTS   = parseInt("{{NUM_ADULTS}}", 10)  || 2;
  const NUM_CHILDREN = parseInt("{{NUM_CHILDREN}}", 10) || 0;
  const ITIN = (function(){
    try{ return JSON.parse(document.getElementById('itin-data').textContent); } catch(e){ return null; }
  })();

  /* ── Header meta strip ── */
  if(ITIN && ITIN.days){
    document.getElementById('meta-duration').innerHTML =
      '<span class="meta-pill">&#9200; ' + ITIN.days + ' days' +
      (ITIN.nights ? ' / ' + ITIN.nights + ' nights' : '') + '</span>';
  }
  const paxLabel = NUM_ADULTS + ' adult' + (NUM_ADULTS!==1?'s':'') +
    (NUM_CHILDREN ? ' + ' + NUM_CHILDREN + ' child' + (NUM_CHILDREN!==1?'ren':'') : '');
  document.getElementById('meta-travelers').innerHTML =
    '<span class="meta-pill">&#128100; ' + paxLabel + '</span>';

  /* ── Itinerary timeline ── */
  const ICONS = {
    flight:'✈️', bus:'🚌', ferry:'⛴️', train:'🚂', car:'🚗',
    hotel:'🏨', transfer:'🚐', activity:'🎯', cruise:'🛳️'
  };
  const TYPE_LABELS = {
    flight:'Flight', bus:'Bus', ferry:'Ferry', train:'Train', car:'Car rental',
    hotel:'Stay', transfer:'Transfer', activity:'Included', cruise:'Cruise'
  };

  (function(){
    const tl = document.getElementById('timeline');
    if(!ITIN || !ITIN.items || !ITIN.items.length){
      tl.innerHTML = '<div class="no-itin">Detailed itinerary is not available for this package in the online system. Your travel agent will provide the full day-by-day programme upon confirmation.</div>';
      return;
    }
    tl.innerHTML = ITIN.items.map((it, i) => {
      const kind = it.kind || 'activity';
      const icon = ICONS[kind] || '📌';
      const typeLabel = TYPE_LABELS[kind] || it.chip || kind;

      let chips = '';
      if(it.detail){
        const parts = it.detail.split(' · ').filter(Boolean);
        chips = parts.map(p => {
          if(/^\d+:\d+/.test(p) || p.includes('→')) return `<span class="chip chip-time">${esc(p)}</span>`;
          if(/\d+h|\d+m/.test(p)) return `<span class="chip chip-dur">${esc(p)}</span>`;
          if(/luggage|baggage|kg/i.test(p)) return `<span class="chip chip-luggage">🧳 ${esc(p)}</span>`;
          if(/board|inclusive|breakfast|half|full|room only/i.test(p)) return `<span class="chip chip-board">${esc(p)}</span>`;
          if(/night/i.test(p)) return `<span class="chip chip-nights">${esc(p)}</span>`;
          return `<span class="chip chip-dur">${esc(p)}</span>`;
        }).join('');
      }

      const starsHtml = it.stars && parseInt(it.stars) > 0
        ? `<div class="tl-stars">${'★'.repeat(Math.min(parseInt(it.stars),5))}</div>` : '';

      return `
        <div class="tl-row">
          <div class="tl-left">
            <div class="tl-line">
              <div class="tl-icon icon-${kind}">${icon}</div>
              ${it.date_label ? `<div class="tl-date-side">${esc(it.date_label)}</div>` : ''}
            </div>
          </div>
          <div class="tl-body">
            <div class="tl-type">${esc(typeLabel)}</div>
            <div class="tl-title">${esc(it.title)}</div>
            ${starsHtml}
            ${chips ? `<div class="tl-chips">${chips}</div>` : ''}
          </div>
        </div>`;
    }).join('');
  })();

  /* ── Passenger sections ── */
  (function(){
    const el = document.getElementById('pax-sections');
    let html = '';
    for(let i=0;i<NUM_ADULTS;i++)   html += paxBlock('adult',i+1,i);
    for(let i=0;i<NUM_CHILDREN;i++) html += paxBlock('child',i+1,NUM_ADULTS+i);
    el.innerHTML = html;
  })();

  function paxBlock(type, num, idx){
    const label = type==='adult' ? 'Traveler '+num+' — Adult' : 'Traveler '+(idx+1)+' — Child';
    return `
      <div class="form-card" data-type="${type}" data-idx="${idx}">
        <div class="pax-header">${label}</div>
        <div class="pax-body">
          <div class="field">
            <label class="fl">Title &amp; full name <span class="req">*</span></label>
            <div class="row3">
              <select id="pt${idx}" class="pax-title" data-idx="${idx}">
                <option value="">—</option>
                <option>Mr.</option>
                <option>Mrs.</option>
                <option>Ms.</option>
                <option>Dr.</option>
              </select>
              <input type="text" id="pf${idx}" class="pax-fname" data-idx="${idx}"
                     placeholder="First name" required>
              <input type="text" id="ps${idx}" class="pax-sname" data-idx="${idx}"
                     placeholder="Surname" required>
            </div>
            <span class="ferr" id="en${idx}">Please enter first and last name.</span>
          </div>
          <div class="field">
            <label class="fl" for="pd${idx}">Date of birth <span class="req">*</span></label>
            <input type="date" id="pd${idx}" class="pax-dob" data-idx="${idx}" required>
            <span class="ferr" id="ed${idx}">Please enter date of birth.</span>
          </div>
          <div class="field">
            <label class="fl" for="pn${idx}">Nationality <span class="req">*</span></label>
            <input type="text" id="pn${idx}" class="pax-nat" data-idx="${idx}"
                   placeholder="e.g. German" required>
            <span class="ferr" id="enat${idx}">Please enter nationality.</span>
          </div>
        </div>
      </div>`;
  }

  /* ── Validation & submit ── */
  function clearErrs(){
    document.querySelectorAll('.ferr,.tc-err').forEach(e=>e.classList.remove('show'));
    document.querySelectorAll('input.err,select.err').forEach(e=>e.classList.remove('err'));
    document.getElementById('err-banner').classList.remove('show');
  }
  function markErr(id, errId){
    const i=document.getElementById(id), e=document.getElementById(errId);
    if(i) i.classList.add('err');
    if(e) e.classList.add('show');
  }

  document.getElementById('reg-form').addEventListener('submit', function(ev){
    ev.preventDefault();
    clearErrs();
    let ok = true;

    document.querySelectorAll('.pax-fname').forEach(inp=>{
      const idx=inp.dataset.idx;
      const sn=document.getElementById('ps'+idx);
      if(!inp.value.trim()||!sn.value.trim()){ markErr('pf'+idx,'en'+idx); ok=false; }
    });
    document.querySelectorAll('.pax-dob').forEach(inp=>{
      const idx=inp.dataset.idx;
      if(!inp.value){ markErr('pd'+idx,'ed'+idx); ok=false; }
    });
    document.querySelectorAll('.pax-nat').forEach(inp=>{
      const idx=inp.dataset.idx;
      if(!inp.value.trim()){ markErr('pn'+idx,'enat'+idx); ok=false; }
    });

    const email=document.getElementById('f-email');
    if(!email.value.trim()||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)){
      markErr('f-email','e-email'); ok=false;
    }
    if(!document.getElementById('f-phone').value.trim()){ markErr('f-phone','e-phone'); ok=false; }
    if(!document.getElementById('f-street').value.trim()){ markErr('f-street','e-street'); ok=false; }
    if(!document.getElementById('f-postal').value.trim()||
       !document.getElementById('f-city').value.trim()){ markErr('f-postal','e-city'); ok=false; }
    if(!document.getElementById('f-country').value.trim()){ markErr('f-country','e-country'); ok=false; }

    ['tc-reservation','tc-terms','tc-data','tc-accuracy'].forEach(id=>{
      if(!document.getElementById(id).checked){
        document.getElementById('e-'+id).classList.add('show'); ok=false;
      }
    });

    if(!ok){
      const b=document.getElementById('err-banner');
      b.textContent='Please fill in all required fields and accept all terms.';
      b.classList.add('show');
      window.scrollTo({top:0,behavior:'smooth'});
      return;
    }

    const passengers=[];
    document.querySelectorAll('.form-card[data-type]').forEach(block=>{
      const idx=block.dataset.idx;
      passengers.push({
        type: block.dataset.type,
        title: (document.getElementById('pt'+idx)||{}).value||'',
        first_name: document.getElementById('pf'+idx).value.trim(),
        last_name: document.getElementById('ps'+idx).value.trim(),
        dob: document.getElementById('pd'+idx).value,
        nationality: document.getElementById('pn'+idx).value.trim(),
      });
    });
    document.getElementById('passengers-json').value=JSON.stringify(passengers);

    const btn=document.getElementById('submit-btn');
    btn.disabled=true; btn.textContent='Sending…';
    this.submit();
  });

  function esc(s){
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
</script>
</body>
</html>
"""
