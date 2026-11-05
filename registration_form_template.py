# Auto-generated — edit this file directly; registration_form_template.py IS the source of truth.
TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{PKG_TITLE}} — {{AGENCY_NAME}}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root{
      --brand:#0d9488;--brand-dark:#0f766e;--brand-light:#f0fdfa;
      --ink:#1e293b;--muted:#64748b;--subtle:#94a3b8;
      --border:#e2e8f0;--bg:#f8fafc;--white:#fff;--red:#dc2626;
    }
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      background:var(--bg);color:var(--ink);min-height:100vh;
      -webkit-font-smoothing:antialiased}

    /* ── Topbar ── */
    .topbar{background:var(--white);padding:.6rem 1.2rem;
      display:flex;align-items:center;justify-content:space-between;
      border-bottom:1px solid var(--border)}
    .topbar-logo{height:28px;max-width:120px;object-fit:contain}
    .topbar-name{color:var(--ink);font-size:.78rem;font-weight:700;letter-spacing:.02em}

    /* ── Hero ── */
    .hero{position:relative;width:100%;height:420px;overflow:hidden;background:#1e293b}
    .hero-img{width:100%;height:100%;object-fit:cover;display:block}
    .hero-ph{width:100%;height:100%;
      background:linear-gradient(135deg,#0f766e 0%,#134e4a 100%)}
    .hero-overlay{position:absolute;inset:0;
      background:linear-gradient(0deg,rgba(15,23,42,.82) 0%,rgba(15,23,42,.3) 55%,transparent 100%);
      display:flex;flex-direction:column;justify-content:flex-end;
      padding:2rem 1.5rem}
    .hero-label{font-size:.65rem;font-weight:600;letter-spacing:.12em;
      text-transform:uppercase;color:rgba(255,255,255,.7);margin-bottom:.5rem}
    .hero h1{font-size:1.65rem;font-weight:800;line-height:1.2;color:#fff;
      margin-bottom:.6rem}
    .hero-route{display:flex;flex-wrap:wrap;align-items:center;gap:.15rem;
      margin-bottom:.8rem}
    .route-chip{color:rgba(255,255,255,.85);font-weight:600;font-size:.78rem}
    .route-arrow{color:rgba(255,255,255,.45);font-size:.72rem;padding:0 .25rem}
    .hero-details{display:flex;flex-wrap:wrap;gap:.6rem .4rem;align-items:center}
    .hero-tag{font-size:.72rem;font-weight:600;color:rgba(255,255,255,.8);
      padding:.25rem .65rem;border:1px solid rgba(255,255,255,.2);
      border-radius:4px;background:rgba(255,255,255,.08)}
    .hero-price-tag{color:#fff;font-weight:800;font-size:.82rem;
      background:var(--brand);border-color:var(--brand);border-radius:4px;
      padding:.25rem .7rem}

    /* ── Page ── */
    .page{max-width:680px;margin:0 auto;padding:1.5rem 1rem 3rem}

    /* ── Section heading ── */
    .sec-title{font-size:.92rem;font-weight:700;color:var(--ink);
      margin:2rem 0 .8rem;padding-bottom:.5rem;
      border-bottom:1px solid var(--border);letter-spacing:.01em}

    /* ── Highlights ── */
    .highlights{display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:1.5rem}
    .hl-card{background:var(--white);border:1px solid var(--border);
      border-radius:6px;padding:.5rem .75rem}
    .hl-val{font-size:.78rem;font-weight:600;color:var(--ink)}

    /* ── Description ── */
    .pkg-desc{font-size:.84rem;color:var(--muted);line-height:1.75;margin-bottom:1.5rem}

    /* ── Departure ── */
    .dep-block{background:var(--brand-light);border:1px solid #99f6e4;
      border-radius:8px;padding:.85rem 1.1rem;margin-bottom:1.5rem;
      display:flex;align-items:center;gap:.8rem}
    .dep-label{font-size:.72rem;font-weight:600;color:var(--muted);text-transform:uppercase;
      letter-spacing:.06em}
    .dep-date{font-size:.95rem;font-weight:700;color:var(--ink);margin-top:.1rem}

    /* ── Hotel cards ── */
    .hotel-grid{display:flex;flex-direction:column;gap:.75rem;margin-bottom:.5rem}
    .hotel-card{display:flex;background:var(--white);border:1px solid var(--border);
      border-radius:8px;overflow:hidden}
    .hc-img{width:160px;min-height:130px;object-fit:cover;flex-shrink:0}
    .hc-img-ph{width:160px;min-height:130px;background:#e2e8f0;flex-shrink:0}
    .hc-body{padding:.75rem 1rem;flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center}
    .hc-name{font-size:.88rem;font-weight:700;color:var(--ink);line-height:1.3;margin-bottom:.15rem}
    .hc-stars{color:#d97706;font-size:.75rem;letter-spacing:.5px;margin-bottom:.3rem}
    .hc-chips{display:flex;flex-wrap:wrap;gap:.3rem}
    .hc-chip{font-size:.68rem;padding:.15rem .45rem;border-radius:3px;font-weight:500;
      background:#f1f5f9;color:var(--muted)}

    /* ── Timeline ── */
    .timeline{display:flex;flex-direction:column;gap:0}
    .tl-row{display:flex;gap:0;position:relative;padding-bottom:.85rem}
    .tl-row:not(:last-child)::before{
      content:'';position:absolute;left:23px;top:40px;
      width:1px;bottom:0;background:var(--border);z-index:0}
    .tl-left{width:48px;flex-shrink:0;display:flex;flex-direction:column;
      align-items:center;padding-top:2px;position:relative;z-index:1}
    .tl-dot{width:10px;height:10px;border-radius:50%;border:2px solid var(--brand);
      background:var(--white);margin-top:6px}
    .tl-date-sm{font-size:.55rem;font-weight:600;color:var(--subtle);
      text-align:center;margin-top:.3rem;text-transform:uppercase;line-height:1.15}
    .tl-body{flex:1;min-width:0;background:var(--white);border:1px solid var(--border);
      border-radius:8px;padding:.65rem .9rem;margin-left:.5rem}
    .tl-type{font-size:.6rem;font-weight:700;text-transform:uppercase;
      letter-spacing:.08em;color:var(--brand);margin-bottom:.15rem}
    .tl-title{font-size:.85rem;font-weight:600;color:var(--ink);margin-bottom:.15rem;line-height:1.3}
    .tl-stars{color:#d97706;font-size:.75rem;letter-spacing:.5px;margin-bottom:.2rem}
    .tl-chips{display:flex;flex-wrap:wrap;gap:.25rem;margin-top:.2rem}
    .chip{font-size:.63rem;padding:.15rem .4rem;border-radius:3px;font-weight:500;
      background:#f1f5f9;color:var(--muted)}
    .chip-green{background:#f0fdf4;color:#166534}
    .chip-amber{background:#fffbeb;color:#92400e}
    .chip-blue{background:#eff6ff;color:#1d4ed8}
    .chip-purple{background:#f5f3ff;color:#5b21b6}

    .no-itin{background:var(--white);border:1px solid var(--border);
      border-radius:8px;padding:1rem 1.2rem;font-size:.84rem;color:var(--muted);line-height:1.6}

    /* ── Notice ── */
    .notice{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;
      padding:.85rem 1rem;margin-bottom:1.2rem}
    .notice-title{font-weight:700;font-size:.82rem;margin-bottom:.2rem;color:#92400e}
    .notice p{font-size:.78rem;color:#78350f;line-height:1.55}

    /* ── Form card ── */
    .form-card{background:var(--white);border:1px solid var(--border);
      border-radius:8px;margin-bottom:1rem;overflow:hidden}
    .pax-header{background:var(--brand-light);padding:.6rem 1.1rem;
      font-size:.7rem;font-weight:700;text-transform:uppercase;
      letter-spacing:.06em;color:var(--brand)}
    .pax-body{padding:.9rem 1.1rem}
    .field{display:flex;flex-direction:column;gap:.2rem;margin-bottom:.6rem}
    .field:last-child{margin-bottom:0}
    label.fl{font-size:.75rem;font-weight:600;color:var(--ink)}
    label.fl .req{color:var(--red)}
    select,input[type=text],input[type=email],input[type=tel],input[type=date]{
      width:100%;padding:.5rem .7rem;
      border:1px solid var(--border);border-radius:6px;
      font-size:.85rem;color:var(--ink);background:var(--white);
      outline:none;transition:border-color .15s;
      -webkit-appearance:none;appearance:none}
    select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%236b7280' d='M6 8L0 0h12z'/%3E%3C/svg%3E");
      background-repeat:no-repeat;background-position:right .7rem center;padding-right:2rem}
    input:focus,select:focus{border-color:var(--brand)}
    input.err,select.err{border-color:var(--red)}
    .ferr{font-size:.7rem;color:var(--red);display:none}
    .ferr.show{display:block}
    .row3{display:grid;grid-template-columns:100px 1fr 1fr;gap:.45rem}
    .row2{display:grid;grid-template-columns:1fr 90px;gap:.45rem}
    .row2b{display:grid;grid-template-columns:110px 1fr;gap:.45rem}
    .divider{border:none;border-top:1px solid var(--border);margin:.55rem 0}

    /* ── T&C ── */
    .tc-body{padding:.9rem 1.1rem}
    .tc-item{display:flex;gap:.6rem;align-items:flex-start;margin-bottom:.6rem}
    .tc-item:last-child{margin-bottom:0}
    .tc-item input[type=checkbox]{width:16px;height:16px;flex-shrink:0;
      accent-color:var(--brand);margin-top:.15rem;cursor:pointer}
    .tc-item label{font-size:.78rem;line-height:1.5;cursor:pointer;color:var(--muted)}
    .tc-item label a{color:var(--brand)}
    .tc-item label strong{color:var(--ink)}
    .tc-err{font-size:.7rem;color:var(--red);display:none;margin-top:.2rem}
    .tc-err.show{display:block}

    /* ── Submit ── */
    .submit-wrap{padding:.9rem 1.1rem;background:var(--bg);border-top:1px solid var(--border)}
    .btn-submit{width:100%;background:var(--brand);color:#fff;border:none;
      border-radius:8px;padding:.75rem 1.5rem;font-size:.92rem;font-weight:700;
      cursor:pointer;transition:background .15s}
    .btn-submit:hover{background:var(--brand-dark)}
    .btn-submit:disabled{opacity:.55;cursor:not-allowed}
    .submit-note{text-align:center;font-size:.7rem;color:var(--subtle);
      margin-top:.45rem;line-height:1.5}
    .err-banner{background:#fef2f2;border:1px solid #fca5a5;color:var(--red);
      border-radius:6px;padding:.55rem .9rem;font-size:.82rem;
      margin-bottom:.9rem;display:none}
    .err-banner.show{display:block}

    .page-footer{text-align:center;padding:1.2rem 1rem;font-size:.68rem;color:var(--subtle);
      border-top:1px solid var(--border);margin-top:.5rem}

    /* ── Timeline detail line ── */
    .tl-detail{font-size:.76rem;color:var(--muted);line-height:1.5;margin-top:.2rem}

    @media(max-width:520px){
      .hero{height:320px}
      .hero h1{font-size:1.35rem}
      .hero-overlay{padding:1.2rem 1rem 1.5rem}
      .hotel-card{flex-direction:column}
      .hc-img,.hc-img-ph{width:100%;height:180px}
      .tl-body{padding:.5rem .7rem}
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
  <div id="hero-img-wrap"></div>
  <div class="hero-overlay">
    <div class="hero-label">{{AGENCY_NAME}} &mdash; Travel Offer</div>
    <h1>{{PKG_TITLE}}</h1>
    <div class="hero-route" id="route-row">{{ROUTE_HTML}}</div>
    <div class="hero-details" id="hero-details"></div>
  </div>
</div>

<div class="page">

  <!-- Highlights -->
  <div class="highlights" id="highlights">{{HIGHLIGHTS_HTML}}</div>

  <!-- Departure -->
  <div class="dep-block" id="dep-block" style="display:none">
    <div>
      <div class="dep-label">Departure</div>
      <div class="dep-date" id="dep-date"></div>
    </div>
  </div>

  <!-- Description -->
  <div class="pkg-desc" id="pkg-desc" style="display:none">{{PKG_DESC}}</div>

  <!-- Hotels -->
  <div class="sec-title" id="hotels-head" style="display:none">Accommodation</div>
  <div class="hotel-grid" id="hotel-grid">{{HOTEL_CARDS_HTML}}</div>

  <!-- Itinerary -->
  <div class="sec-title">Itinerary</div>
  <div class="timeline" id="timeline">
    <div style="color:var(--muted);font-size:.84rem;padding:.5rem 0">Loading&hellip;</div>
  </div>

  <!-- Reservation notice -->
  <div class="notice" style="margin-top:1.5rem">
    <div>
      <div class="notice-title">This is a reservation request, not a confirmed booking</div>
      <p>By submitting this form you place a <strong>reservation request</strong>.
         Your travel agent at <strong>{{AGENCY_NAME}}</strong> will contact you to
         confirm availability and price. No payment is taken until you receive written confirmation.</p>
    </div>
  </div>

  <div class="err-banner" id="err-banner"></div>

  <form id="reg-form" method="post"
        action="/register/{{AGENT_ID}}/{{PACKAGE_ID}}" novalidate>

    <div class="sec-title">Traveller Details</div>
    <div id="pax-sections"></div>

    <div class="sec-title">Contact Details</div>
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

    <div class="sec-title">Terms &amp; Conditions</div>
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

      <div style="padding:.9rem 1.1rem;border-top:1px solid var(--border)">
        <div style="font-size:.72rem;font-weight:600;color:var(--muted);margin-bottom:.4rem;text-transform:uppercase;letter-spacing:.06em">Verification</div>
        <div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap">
          <span id="captcha-question" style="font-size:.95rem;font-weight:700;color:var(--ink)"></span>
          <span style="color:var(--muted)">=</span>
          <input type="number" id="captcha-input" name="captcha_answer" placeholder="?" autocomplete="off"
                 style="width:72px;border:1px solid var(--border);border-radius:6px;padding:.45rem .6rem;font-size:.95rem;text-align:center">
          <input type="hidden" name="captcha_expected" id="captcha-expected">
        </div>
        <span id="e-captcha" class="ferr" style="display:none;margin-top:.25rem">Please answer correctly.</span>
      </div>

      <div class="submit-wrap">
        <button type="submit" class="btn-submit" id="submit-btn">Submit reservation request</button>
        <div class="submit-note">
          Your travel agent will contact you to confirm availability and finalise your booking.
        </div>
      </div>
    </div>

    <input type="hidden" name="passengers_json" id="passengers-json">
  </form>

  <div class="page-footer">
    {{AGENCY_NAME}} &middot; All prices per person, subject to availability
  </div>
</div>

<script type="application/json" id="itin-data">{{ITINERARY_JSON}}</script>
<script type="application/json" id="gallery-data">{{GALLERY_JSON}}</script>
<script>
  var NUM_ADULTS   = parseInt("{{NUM_ADULTS}}", 10)  || 2;
  var NUM_CHILDREN = parseInt("{{NUM_CHILDREN}}", 10) || 0;
  var PRICE_STR    = "{{PRICE_STR}}";
  var DEP_DATE     = "{{DEPARTURE_DATE}}";
  var ITIN, GALLERY;
  try{ ITIN = JSON.parse(document.getElementById('itin-data').textContent); } catch(e){ ITIN = null; }
  try{ GALLERY = JSON.parse(document.getElementById('gallery-data').textContent); } catch(e){ GALLERY = []; }

  /* ── Hero image ── */
  (function(){
    var wrap = document.getElementById('hero-img-wrap');
    if(GALLERY && GALLERY.length){
      wrap.innerHTML = '<img class="hero-img" src="'+esc(GALLERY[0])+'" alt="Destination">';
    } else {
      wrap.innerHTML = '<div class="hero-ph"></div>';
    }
  })();

  /* ── Hero detail tags ── */
  (function(){
    var el = document.getElementById('hero-details');
    var tags = [];
    if(ITIN && ITIN.days)
      tags.push(ITIN.days + ' Days / ' + (ITIN.nights||0) + ' Nights');
    var pax = NUM_ADULTS + ' Adult' + (NUM_ADULTS!==1?'s':'');
    if(NUM_CHILDREN) pax += ', ' + NUM_CHILDREN + ' Child' + (NUM_CHILDREN!==1?'ren':'');
    tags.push(pax);
    if(PRICE_STR) tags.push('<span class="hero-price-tag">'+esc(PRICE_STR)+' / person</span>');
    el.innerHTML = tags.map(function(t){
      if(t.indexOf('hero-price-tag')!==-1) return t;
      return '<span class="hero-tag">'+t+'</span>';
    }).join('');
  })();

  /* ── Show conditional sections ── */
  if(DEP_DATE){
    document.getElementById('dep-block').style.display = '';
    document.getElementById('dep-date').textContent = DEP_DATE;
  }
  if(document.getElementById('pkg-desc').textContent.trim())
    document.getElementById('pkg-desc').style.display = '';
  if(document.getElementById('hotel-grid').children.length > 0)
    document.getElementById('hotels-head').style.display = '';

  /* ── Itinerary ── */
  var TYPE_LABELS = {
    flight:'Flight', bus:'Transport', ferry:'Ferry', train:'Train', car:'Car Rental',
    hotel:'Accommodation', transfer:'Transfer', activity:'Excursion', cruise:'Cruise',
    tour:'Tour', supplement:'Supplement'
  };

  function renderItem(it){
    var kind = it.kind || 'activity';
    var typeLabel = (TYPE_LABELS[kind] || it.chip || kind).toUpperCase();

    var headerExtra = '';
    if(it.provider) headerExtra = ' &middot; ' + esc(it.provider);

    var starsHtml = '';
    if(it.stars && parseInt(it.stars) > 0)
      starsHtml = '<div class="tl-stars">' + Array(Math.min(parseInt(it.stars),5)+1).join('&#9733;') + '</div>';

    var detailParts = [];
    if(kind==='flight'||kind==='ferry'||kind==='bus'||kind==='train'||kind==='car'){
      var infoParts = [];
      if(it.time)     infoParts.push(esc(it.time));
      if(it.duration) infoParts.push(esc(it.duration));
      if(it.stops)    infoParts.push(esc(it.stops));
      else if(kind==='flight') infoParts.push('Direct');
      if(it.overnight) infoParts.push('Overnight');
      if(infoParts.length) detailParts.push(infoParts.join(' &middot; '));
      if(it.baggage) detailParts.push('Baggage: ' + esc(it.baggage));
    } else if(kind==='hotel'){
      var hotelParts = [];
      if(it.nights && it.nights>0) hotelParts.push(it.nights+' Night'+(it.nights!==1?'s':''));
      if(it.board) hotelParts.push(esc(it.board));
      if(it.room)  hotelParts.push(esc(it.room));
      if(hotelParts.length) detailParts.push(hotelParts.join(' &middot; '));
      if(it.date_range) detailParts.push(esc(it.date_range));
    } else if(kind==='transfer'){
      var trParts = [];
      if(it.time) trParts.push(esc(it.time) + ' pickup');
      if(it.provider) trParts.push(esc(it.provider));
      if(it.overnight) trParts.push('Overnight');
      if(trParts.length) detailParts.push(trParts.join(' &middot; '));
      headerExtra = '';
    } else if(kind==='cruise'){
      var crParts = [];
      if(it.nights && it.nights>0) crParts.push(it.nights+' Night'+(it.nights!==1?'s':''));
      if(crParts.length) detailParts.push(crParts.join(' &middot; '));
    } else if(kind==='activity'){
      if(it.pax && it.pax>0) detailParts.push(it.pax+' person'+(it.pax!==1?'s':''));
    } else if(kind==='tour'){
      if(it.date_range) detailParts.push(esc(it.date_range));
      if(it.modality) detailParts.push(esc(it.modality));
    } else if(kind==='supplement'){
      if(it.pax && it.pax>0) detailParts.push(it.pax+' person'+(it.pax!==1?'s':''));
    }

    var detailHtml = detailParts.length
      ? '<div class="tl-detail">' + detailParts.join('<br>') + '</div>' : '';

    var dateHtml = '';
    if(it.date_label){
      var p = it.date_label.trim().split(/\\s+/);
      var parts = [];
      for(var i=0;i<p.length;i++) parts.push(esc(p[i]));
      dateHtml = '<div class="tl-date-sm">'+parts.join('<br>')+'</div>';
    }

    return '<div class="tl-row">'+
      '<div class="tl-left"><div class="tl-dot"></div>'+dateHtml+'</div>'+
      '<div class="tl-body">'+
        '<div class="tl-type">'+esc(typeLabel)+headerExtra+'</div>'+
        '<div class="tl-title">'+esc(it.title||'')+'</div>'+
        starsHtml+detailHtml+
      '</div></div>';
  }

  (function(){
    var tl = document.getElementById('timeline');
    if(!ITIN || !ITIN.items || !ITIN.items.length){
      tl.innerHTML = '<div class="no-itin">Detailed itinerary is not yet available for this package. Your travel agent will provide the full programme upon confirmation.</div>';
      return;
    }
    tl.innerHTML = ITIN.items.map(renderItem).join('');
  })();

  /* ── Passenger sections ── */
  (function(){
    var el = document.getElementById('pax-sections');
    var html = '';
    for(var i=0;i<NUM_ADULTS;i++)   html += paxBlock('adult',i+1,i);
    for(var i=0;i<NUM_CHILDREN;i++) html += paxBlock('child',i+1,NUM_ADULTS+i);
    el.innerHTML = html;
  })();

  function paxBlock(type, num, idx){
    var label = type==='adult' ? 'Traveller '+num+' &mdash; Adult' : 'Traveller '+(idx+1)+' &mdash; Child';
    return '<div class="form-card" data-type="'+type+'" data-idx="'+idx+'">'+
      '<div class="pax-header">'+label+'</div>'+
      '<div class="pax-body">'+
        '<div class="field">'+
          '<label class="fl">Title &amp; full name <span class="req">*</span></label>'+
          '<div class="row3">'+
            '<select id="pt'+idx+'" class="pax-title" data-idx="'+idx+'"><option value="">\\u2014</option><option>Mr.</option><option>Mrs.</option><option>Ms.</option><option>Dr.</option></select>'+
            '<input type="text" id="pf'+idx+'" class="pax-fname" data-idx="'+idx+'" placeholder="First name" required>'+
            '<input type="text" id="ps'+idx+'" class="pax-sname" data-idx="'+idx+'" placeholder="Surname" required>'+
          '</div>'+
          '<span class="ferr" id="en'+idx+'">Please enter first and last name.</span>'+
        '</div>'+
        '<div class="field">'+
          '<label class="fl" for="pd'+idx+'">Date of birth <span class="req">*</span></label>'+
          '<input type="date" id="pd'+idx+'" class="pax-dob" data-idx="'+idx+'" required>'+
          '<span class="ferr" id="ed'+idx+'">Please enter date of birth.</span>'+
        '</div>'+
        '<div class="field">'+
          '<label class="fl" for="pn'+idx+'">Nationality <span class="req">*</span></label>'+
          '<input type="text" id="pn'+idx+'" class="pax-nat" data-idx="'+idx+'" placeholder="e.g. German" required>'+
          '<span class="ferr" id="enat'+idx+'">Please enter nationality.</span>'+
        '</div>'+
      '</div></div>';
  }

  /* ── CAPTCHA ── */
  (function(){
    var a = Math.floor(Math.random()*20)+1;
    var b = Math.floor(Math.random()*20)+1;
    document.getElementById('captcha-question').textContent = a + ' + ' + b;
    document.getElementById('captcha-expected').value = a + b;
  })();

  /* ── Validation ── */
  function clearErrs(){
    document.querySelectorAll('.ferr,.tc-err').forEach(function(e){e.classList.remove('show')});
    document.querySelectorAll('input.err,select.err').forEach(function(e){e.classList.remove('err')});
    document.getElementById('err-banner').classList.remove('show');
    document.getElementById('e-captcha').style.display='none';
  }
  function markErr(id, errId){
    var i=document.getElementById(id), e=document.getElementById(errId);
    if(i) i.classList.add('err');
    if(e) e.classList.add('show');
  }

  document.getElementById('reg-form').addEventListener('submit', function(ev){
    ev.preventDefault();
    clearErrs();
    var ok = true;
    document.querySelectorAll('.pax-fname').forEach(function(inp){
      var idx=inp.dataset.idx;
      var sn=document.getElementById('ps'+idx);
      if(!inp.value.trim()||!sn.value.trim()){ markErr('pf'+idx,'en'+idx); ok=false; }
    });
    document.querySelectorAll('.pax-dob').forEach(function(inp){
      var idx=inp.dataset.idx;
      if(!inp.value){ markErr('pd'+idx,'ed'+idx); ok=false; }
    });
    document.querySelectorAll('.pax-nat').forEach(function(inp){
      var idx=inp.dataset.idx;
      if(!inp.value.trim()){ markErr('pn'+idx,'enat'+idx); ok=false; }
    });
    var email=document.getElementById('f-email');
    if(!email.value.trim()||!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email.value)){
      markErr('f-email','e-email'); ok=false;
    }
    if(!document.getElementById('f-phone').value.trim()){ markErr('f-phone','e-phone'); ok=false; }
    if(!document.getElementById('f-street').value.trim()){ markErr('f-street','e-street'); ok=false; }
    if(!document.getElementById('f-postal').value.trim()||
       !document.getElementById('f-city').value.trim()){ markErr('f-postal','e-city'); ok=false; }
    if(!document.getElementById('f-country').value.trim()){ markErr('f-country','e-country'); ok=false; }
    ['tc-reservation','tc-terms','tc-data','tc-accuracy'].forEach(function(id){
      if(!document.getElementById(id).checked){
        document.getElementById('e-'+id).classList.add('show'); ok=false;
      }
    });
    var ci = parseInt(document.getElementById('captcha-input').value,10);
    var ce = parseInt(document.getElementById('captcha-expected').value,10);
    if(isNaN(ci)||ci!==ce){ document.getElementById('e-captcha').style.display='block'; ok=false; }
    if(!ok){
      var b=document.getElementById('err-banner');
      b.textContent='Please complete all required fields and accept the terms.';
      b.classList.add('show');
      window.scrollTo({top:0,behavior:'smooth'});
      return;
    }
    var passengers=[];
    document.querySelectorAll('.form-card[data-type]').forEach(function(block){
      var idx=block.dataset.idx;
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
    var btn=document.getElementById('submit-btn');
    btn.disabled=true; btn.textContent='Submitting\\u2026';
    this.submit();
  });

  function esc(s){
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
</script>
</body>
</html>
"""
