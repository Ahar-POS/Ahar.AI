import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './LandingPage.css';

const stats = [
  { value: '30%', label: 'Less food waste', sub: 'across pilot kitchens' },
  { value: '10 hrs', label: 'Saved per owner / week', sub: 'on inventory + ordering' },
  { value: '98%', label: 'Demand-forecast accuracy', sub: 'on top-selling items' },
  { value: '₹2.4L', label: 'Avg monthly savings', sub: 'on food + labour cost' },
];

const capabilities = [
  {
    eyebrow: '01 · Billing',
    title: 'Billing that just works',
    body: 'Take orders and print bills from your phone. GST-ready, KOT prints to the kitchen, and every payment — UPI, cash, card — in one place.',
    bullets: ['GST bills, ready for your CA', 'Prints KOTs to the kitchen', 'UPI, cash, card, wallet'],
  },
  {
    eyebrow: '02 · Inventory',
    title: 'Know your stock, always',
    body: 'Every dish you sell deducts its ingredients automatically. See what\u2019s running low, what\u2019s about to expire, and what needs reordering — without counting anything by hand.',
    bullets: ['Auto-deducts ingredients per dish', 'Warns before spices go stale', 'Tracks expiry dates for you'],
  },
  {
    eyebrow: '03 · Forecasting',
    title: 'Know what will sell tomorrow',
    body: 'Ahar.AI learns your kitchen — your menu, your weekends, your festival rush — and tells you what to prep and what to order. So nothing runs out, and nothing gets wasted.',
    bullets: ['Dish-level demand predictions', 'Diwali, Eid, Onam built-in', 'Adjusts for weather & weekends'],
  },
  {
    eyebrow: '04 · AI Agents',
    title: 'A back office that runs itself',
    body: 'Your AI team works 24×7 — one watches sales, one watches stock, one watches expiry, one watches your bills. They flag problems before they cost you money.',
    bullets: ['Alerts when sales drop', 'Drafts purchase orders for you', 'One-tap approvals on your phone'],
  },
  {
    eyebrow: '05 · P&L',
    title: 'Profit & loss in plain English',
    body: 'See how much you made today, what you spent on food and staff, and where your money is going. Ask "why was last Tuesday slow?" and get a straight answer.',
    bullets: ['Daily profit snapshot', 'Food & staff cost at a glance', 'Ask questions, get answers'],
  },
  {
    eyebrow: '06 · Approvals',
    title: 'Purchase orders, done for you',
    body: 'Ahar.AI drafts the order, sends it to your supplier, and scans the bill when it arrives. You just tap to approve — from anywhere.',
    bullets: ['AI drafts your orders', 'Scans vendor bills automatically', 'Approve from your phone'],
  },
];

const steps = [
  {
    n: '01',
    title: 'Connect your data',
    body: 'Plug in your menu, suppliers, and last 60 days of orders. Or start fresh — we generate a starter recipe BOM and supplier list for Indian kitchens.',
  },
  {
    n: '02',
    title: 'AI learns your patterns',
    body: 'In 7 days, Ahar.AI maps your demand curves, festival spikes, item-level shelf life, and supplier reliability. No analyst required.',
  },
  {
    n: '03',
    title: 'Approve, don\u2019t operate',
    body: 'Your AI agents draft the daily POs, flag the slow-moving SKUs, and surface the actions that matter. You approve in one tap from the Command Center.',
  },
];

const agentRows = [
  { name: 'Revenue Monitor', body: 'Watches daily revenue, table turn, and AOV. Flags anomalies the moment they happen, not next month.' },
  { name: 'Inventory Agent', body: 'Tracks stock against recipe BOM, predicts the next stockout, and proposes a PO before you run out of paneer at peak hour.' },
  { name: 'Expiry Tracker', body: 'Knows the shelf-life of every batch — from spice to dairy. Suggests "expiry specials" to move at-risk stock through your menu.' },
  { name: 'Smart Approvals', body: 'Learns your spend thresholds. Auto-approves routine reorders. Pauses anything that looks off and pings you.' },
];

const indiaFit = [
  'GST + e-invoicing built in',
  'Festival-aware forecasting (Diwali · Eid · Navratri · Onam · Pongal)',
  'Spice & masala inventory with shelf-life',
  'UPI · cash · card · wallet · Swiggy / Zomato reconciliation',
  'Regional units \u2014 kg, litre, dozen, plate, packet',
  'Hindi & regional language menu support',
];

const industries = [
  'Cloud kitchens',
  'Biryani brands',
  'Tiffin & dabba services',
  'Dhabas',
  'Mithai shops',
  'Caf\u00e9s',
  'QSR chains',
  'Multi-outlet groups',
];

const faqItems = [
  {
    q: 'What is the best AI restaurant management software in India?',
    a: 'Ahar.AI is purpose-built as an AI restaurant management software for India. It combines POS, inventory, demand forecasting, and an autonomous agent layer that proactively flags low stock, expiring items, and revenue anomalies. Unlike generic restaurant POS systems, it learns the patterns of your kitchen and runs decisions for you to approve in one tap.',
  },
  {
    q: 'Can AI really reduce food waste in a restaurant?',
    a: 'Yes \u2014 measurably. Ahar.AI\u2019s pilot kitchens have cut food waste by an average of 30% by combining recipe-level inventory tracking, batch-level shelf-life monitoring, and item-level demand forecasts. The system spots at-risk stock early and suggests menu specials or supplier adjustments before the waste happens.',
  },
  {
    q: 'How does demand forecasting work for Indian restaurants during festivals like Diwali and Eid?',
    a: 'Most generic forecasting tools miss Indian festival spikes entirely. Ahar.AI\u2019s forecaster includes a built-in Indian holiday calendar and learns the exact lift each festival drives at your restaurant \u2014 a Bangalore caf\u00e9 spikes differently for Diwali than a Hyderabadi biryani brand spikes for Eid. The model adjusts its predictions and your purchase orders automatically.',
  },
  {
    q: 'Is Ahar.AI suitable for cloud kitchens and biryani brands?',
    a: 'Especially so. Cloud kitchens and biryani brands operate on tight margins, batch cooking, and aggregator-driven demand. Ahar.AI gives you cloud kitchen analytics tuned for India \u2014 brand-level P&L, aggregator reconciliation, batch cost tracking, and demand forecasts that respect your prep windows.',
  },
  {
    q: 'Can Ahar.AI handle a tiffin service or dabba subscription model?',
    a: 'Yes. Ahar.AI supports tiffin / dabba service management \u2014 daily subscription rosters, route-aware preparation forecasts, and monthly billing for recurring customers. It\u2019s the only restaurant management software in India that treats tiffin services as a first-class business model rather than an afterthought.',
  },
  {
    q: 'Does Ahar.AI work for dhabas and small restaurants in tier-2 cities?',
    a: 'Absolutely. Ahar.AI is mobile-first, runs on a budget Android device, supports cash-heavy workflows, and is priced for independent operators. Whether you run a highway dhaba, a single-location family restaurant, or a small chain in a tier-2 city, the setup takes under ten minutes.',
  },
  {
    q: 'Does Ahar.AI handle GST billing and Indian compliance?',
    a: 'Yes. GST billing software for restaurants is core to Ahar.AI \u2014 GSTIN-aware invoices, HSN/SAC codes, CGST/SGST/IGST splits, and e-invoicing for businesses above the turnover threshold. Daily, monthly, and quarterly summaries are exportable for your CA.',
  },
  {
    q: 'How is Ahar.AI different from a regular restaurant POS like Petpooja or Posist?',
    a: 'Traditional restaurant POS systems record what happened. Ahar.AI predicts what will happen, recommends what to do, and \u2014 with your approval \u2014 acts on it. The AI agent layer (revenue monitor, inventory agent, expiry tracker, smart approvals) is the difference between a billing system and a back office that runs itself.',
  },
  {
    q: 'What does an AI agent for restaurant operations actually do?',
    a: 'Each Ahar.AI agent owns one job. The Revenue Monitor watches sales for anomalies. The Inventory Agent forecasts stockouts and drafts POs. The Expiry Tracker proposes specials for at-risk batches. The Smart Approvals agent learns your spend patterns and auto-approves routine reorders. You see one feed of decisions to approve, not a dashboard of dashboards.',
  },
  {
    q: 'How quickly can I set up Ahar.AI?',
    a: 'Most restaurants are live in under ten minutes. Import your menu (or pick a starter template), connect your supplier list, and start billing the same day. The AI agents need around 7 days of order history before their forecasts and recommendations stabilise.',
  },
];

const footerColumns = [
  {
    title: 'Product',
    links: [
      { label: 'AI POS', to: '/features' },
      { label: 'Inventory', to: '/features' },
      { label: 'Demand forecasting', to: '/features' },
      { label: 'Autonomous agents', to: '/features' },
      { label: 'P&L tracker', to: '/features' },
    ],
  },
  {
    title: 'Solutions',
    links: [
      { label: 'Cloud kitchens', to: '/features' },
      { label: 'Biryani brands', to: '/features' },
      { label: 'Tiffin services', to: '/features' },
      { label: 'Dhabas', to: '/features' },
      { label: 'Mithai shops', to: '/features' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'About', to: '/about' },
      { label: 'Pricing', to: '/pricing' },
      { label: 'Sign in', to: '/signin' },
      { label: 'Get started', to: '/signup' },
    ],
  },
];

export default function LandingPage() {
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('lp-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -60px 0px' }
    );

    document.querySelectorAll('.lp-reveal').forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  const primaryCtaTo = isAuthenticated ? '/home' : '/signup';
  const primaryCtaLabel = isAuthenticated ? 'Go to dashboard' : 'Start free trial';

  return (
    <div className="lp-root">
      <header className="lp-nav">
        <div className="lp-container lp-nav-inner">
          <Link to="/" className="lp-brand" aria-label="Ahar.AI home">
            <span className="lp-brand-mark" aria-hidden="true">A</span>
            <span className="lp-brand-text">Ahar<span className="lp-brand-dot">.</span>AI</span>
          </Link>
          <nav className="lp-nav-links" aria-label="Primary">
            <a href="#capabilities">Product</a>
            <a href="#how">How it works</a>
            <a href="#india">For India</a>
            <Link to="/pricing">Pricing</Link>
            <Link to="/about">About</Link>
          </nav>
          <div className="lp-nav-ctas">
            {isAuthenticated ? (
              <Link to="/home" className="lp-btn lp-btn-primary lp-btn-sm">Go to dashboard</Link>
            ) : (
              <>
                <Link to="/signin" className="lp-nav-signin">Sign in</Link>
                <Link to="/signup" className="lp-btn lp-btn-primary lp-btn-sm">Get started free</Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main>
        <section className="lp-hero" aria-labelledby="lp-hero-title">
          <div className="lp-hero-bg" aria-hidden="true">
            <div className="lp-hero-blob lp-hero-blob-a" />
            <div className="lp-hero-blob lp-hero-blob-b" />
          </div>
          <div className="lp-container lp-hero-grid">
            <div className="lp-hero-copy">
              <span className="lp-pill">
                <span className="lp-pill-dot" aria-hidden="true" />
                Built for Indian restaurants
              </span>
              <h1 id="lp-hero-title" className="lp-display">
                The <em>AI restaurant management software</em> that runs your kitchen.
              </h1>
              <p className="lp-lede">
                Ahar.AI is the AI-powered restaurant POS, inventory and demand-forecasting platform that helps Indian restaurant owners cut food waste by 30% and reclaim 10 hours every week.
              </p>
              <div className="lp-hero-ctas">
                <Link to={primaryCtaTo} className="lp-btn lp-btn-primary">
                  {primaryCtaLabel} <span aria-hidden="true">→</span>
                </Link>
                <Link to="/about" className="lp-btn lp-btn-ghost">
                  Book a demo
                </Link>
              </div>
              <p className="lp-hero-meta">
                No credit card · GST-ready · Live in under 10 minutes
              </p>
            </div>
            <div className="lp-hero-visual" aria-hidden="true">
              <DashboardMockup />
            </div>
          </div>
        </section>

        <section className="lp-outcomes lp-reveal" aria-labelledby="lp-outcomes-title">
          <div className="lp-container">
            <h2 id="lp-outcomes-title" className="lp-section-title">
              Real outcomes for real kitchens.
            </h2>
            <div className="lp-stat-grid">
              {stats.map((stat) => (
                <div key={stat.label} className="lp-stat">
                  <div className="lp-stat-value">{stat.value}</div>
                  <div className="lp-stat-label">{stat.label}</div>
                  <div className="lp-stat-sub">{stat.sub}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="capabilities" className="lp-capabilities lp-reveal" aria-labelledby="lp-cap-title">
          <div className="lp-container">
            <div className="lp-section-head">
              <span className="lp-eyebrow">One platform · six modules</span>
              <h2 id="lp-cap-title" className="lp-section-title">
                The complete AI back office for your restaurant.
              </h2>
              <p className="lp-section-lede">
                Restaurant POS. Inventory. Demand forecasting. Autonomous agents. Profit &amp; loss. Smart approvals. One platform, one source of truth, one bill.
              </p>
            </div>
            <div className="lp-cap-grid">
              {capabilities.map((c) => (
                <article key={c.title} className="lp-cap-card">
                  <div className="lp-cap-eyebrow">{c.eyebrow}</div>
                  <h3 className="lp-cap-title">{c.title}</h3>
                  <p className="lp-cap-body">{c.body}</p>
                  <ul className="lp-cap-bullets">
                    {c.bullets.map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="how" className="lp-how lp-reveal" aria-labelledby="lp-how-title">
          <div className="lp-container">
            <div className="lp-section-head">
              <span className="lp-eyebrow">How it works</span>
              <h2 id="lp-how-title" className="lp-section-title">
                Set up in an afternoon. Run smarter from day one.
              </h2>
            </div>
            <div className="lp-how-grid">
              {steps.map((s) => (
                <div key={s.n} className="lp-step">
                  <div className="lp-step-num">{s.n}</div>
                  <h3 className="lp-step-title">{s.title}</h3>
                  <p className="lp-step-body">{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-agents lp-reveal" aria-labelledby="lp-agents-title">
          <div className="lp-container lp-agents-grid">
            <div className="lp-agents-copy">
              <span className="lp-eyebrow lp-eyebrow-light">Autonomous AI agents</span>
              <h2 id="lp-agents-title" className="lp-section-title lp-section-title-light">
                Four AI agents on duty. One owner in charge.
              </h2>
              <p className="lp-section-lede lp-section-lede-light">
                Most restaurant software gives you dashboards. Ahar.AI gives you a back office that proposes the next move and waits for your nod.
              </p>
              <Link to="/features" className="lp-btn lp-btn-primary-light">
                See the agents in action <span aria-hidden="true">→</span>
              </Link>
            </div>
            <div className="lp-agents-list">
              {agentRows.map((a) => (
                <div key={a.name} className="lp-agent-row">
                  <div className="lp-agent-pulse" aria-hidden="true">
                    <span /><span /><span />
                  </div>
                  <div>
                    <div className="lp-agent-name">{a.name}</div>
                    <p className="lp-agent-body">{a.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="india" className="lp-india lp-reveal" aria-labelledby="lp-india-title">
          <div className="lp-container">
            <div className="lp-section-head">
              <span className="lp-eyebrow">Built for India</span>
              <h2 id="lp-india-title" className="lp-section-title">
                Designed for the way Indian restaurants actually work.
              </h2>
              <p className="lp-section-lede">
                Ahar.AI is built ground-up for Indian kitchens &mdash; the menus, the cuisines, the suppliers, the festivals, the GST, the UPI, the cash, the chaos.
              </p>
            </div>
            <ul className="lp-india-grid">
              {indiaFit.map((item) => (
                <li key={item} className="lp-india-item">
                  <span className="lp-tick" aria-hidden="true">✓</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <div className="lp-industries">
              <span className="lp-industries-label">Industries we power</span>
              <div className="lp-industries-list">
                {industries.map((ind, i) => (
                  <span key={ind} className="lp-industry">
                    {ind}
                    {i < industries.length - 1 && <span className="lp-industry-dot" aria-hidden="true"> · </span>}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="lp-quote lp-reveal" aria-label="Customer testimonial">
          <div className="lp-container">
            <blockquote className="lp-quote-block">
              <p className="lp-quote-text">
                "We used to lose two hours every morning chasing inventory. With Ahar.AI, the AI drafts our purchase orders overnight and our chef just approves them. It's the first software that feels like it actually understands an Indian kitchen."
              </p>
              <footer className="lp-quote-meta">
                <span className="lp-quote-name">Owner, multi-outlet biryani brand</span>
                <span className="lp-quote-loc">Bengaluru, India</span>
              </footer>
            </blockquote>
          </div>
        </section>

        <section className="lp-pricing-teaser lp-reveal" aria-labelledby="lp-pricing-title">
          <div className="lp-container lp-pricing-inner">
            <div>
              <span className="lp-eyebrow">Simple, transparent pricing</span>
              <h2 id="lp-pricing-title" className="lp-section-title">
                Plans built for independent restaurants and growing chains.
              </h2>
              <p className="lp-section-lede">
                Starter plans from a flat monthly fee. Cancel any time. No per-bill commission, no per-employee tax.
              </p>
            </div>
            <div className="lp-pricing-cta">
              <Link to="/pricing" className="lp-btn lp-btn-primary">
                See pricing <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>
        </section>

        <section className="lp-faq lp-reveal" aria-labelledby="lp-faq-title">
          <div className="lp-container lp-faq-grid">
            <div className="lp-faq-head">
              <span className="lp-eyebrow">FAQ</span>
              <h2 id="lp-faq-title" className="lp-section-title">
                Questions Indian restaurant owners ask us.
              </h2>
              <p className="lp-section-lede">
                Honest answers about how Ahar.AI handles GST, festivals, dhabas, tiffin services, biryani brands, and the rest of the Indian restaurant world.
              </p>
            </div>
            <div className="lp-faq-list">
              {faqItems.map((f, i) => (
                <details key={f.q} className="lp-faq-item" open={i === 0}>
                  <summary className="lp-faq-q">
                    <span>{f.q}</span>
                    <span className="lp-faq-icon" aria-hidden="true" />
                  </summary>
                  <p className="lp-faq-a">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-final-cta lp-reveal" aria-labelledby="lp-final-title">
          <div className="lp-container lp-final-inner">
            <h2 id="lp-final-title" className="lp-final-title">
              Run your restaurant with an AI back office, not another dashboard.
            </h2>
            <p className="lp-final-lede">
              Start free. Be live in under ten minutes. Watch your AI agents earn their keep by week two.
            </p>
            <div className="lp-final-ctas">
              <Link to={primaryCtaTo} className="lp-btn lp-btn-primary-light">
                {primaryCtaLabel} <span aria-hidden="true">→</span>
              </Link>
              <Link to="/about" className="lp-btn lp-btn-ghost-light">
                Talk to founders
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-container lp-footer-grid">
          <div className="lp-footer-brand">
            <Link to="/" className="lp-brand">
              <span className="lp-brand-mark" aria-hidden="true">A</span>
              <span className="lp-brand-text">Ahar<span className="lp-brand-dot">.</span>AI</span>
            </Link>
            <p className="lp-footer-tag">
              The AI restaurant management software for India. POS, inventory, demand forecasting and autonomous agents — one platform.
            </p>
            <p className="lp-footer-loc">Made in India for Indian restaurants.</p>
          </div>
          {footerColumns.map((col) => (
            <div key={col.title} className="lp-footer-col">
              <div className="lp-footer-col-title">{col.title}</div>
              <ul>
                {col.links.map((l) => (
                  <li key={l.label}><Link to={l.to}>{l.label}</Link></li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="lp-container lp-footer-bottom">
          <p>&copy; {new Date().getFullYear()} Ahar.AI. All rights reserved.</p>
          <p className="lp-footer-legal">
            <Link to="/about">Privacy</Link>
            <span aria-hidden="true"> · </span>
            <Link to="/about">Terms</Link>
          </p>
        </div>
      </footer>
    </div>
  );
}

function DashboardMockup() {
  return (
    <div className="lp-mockup">
      <div className="lp-mockup-chrome">
        <span className="lp-mockup-dot lp-mockup-dot-r" />
        <span className="lp-mockup-dot lp-mockup-dot-y" />
        <span className="lp-mockup-dot lp-mockup-dot-g" />
        <span className="lp-mockup-url">ahar.ai / command-center</span>
      </div>
      <div className="lp-mockup-body">
        <aside className="lp-mockup-side">
          <div className="lp-mockup-side-brand">A</div>
          <span className="lp-mockup-side-item lp-mockup-side-active" />
          <span className="lp-mockup-side-item" />
          <span className="lp-mockup-side-item" />
          <span className="lp-mockup-side-item" />
          <span className="lp-mockup-side-item" />
        </aside>
        <div className="lp-mockup-main">
          <div className="lp-mockup-head">
            <div className="lp-mockup-head-title">Today · Command Center</div>
            <div className="lp-mockup-head-sub">4 actions waiting · ₹42,180 revenue · 98% forecast hit</div>
          </div>
          <div className="lp-mockup-grid">
            <div className="lp-mockup-card lp-mockup-card-accent">
              <div className="lp-mockup-card-label">Revenue today</div>
              <div className="lp-mockup-card-value">₹42,180</div>
              <div className="lp-mockup-spark">
                <span /><span /><span /><span /><span /><span /><span /><span />
              </div>
            </div>
            <div className="lp-mockup-card">
              <div className="lp-mockup-card-label">Action queue</div>
              <div className="lp-mockup-action">
                <span className="lp-mockup-action-pill lp-mockup-action-amber">Low</span>
                <span>Paneer · approve PO</span>
              </div>
              <div className="lp-mockup-action">
                <span className="lp-mockup-action-pill lp-mockup-action-rose">Expiry</span>
                <span>Curd · push special</span>
              </div>
              <div className="lp-mockup-action">
                <span className="lp-mockup-action-pill lp-mockup-action-emerald">PO</span>
                <span>Veggies · auto-sent</span>
              </div>
            </div>
            <div className="lp-mockup-card">
              <div className="lp-mockup-card-label">Top sellers · forecast</div>
              <div className="lp-mockup-bar">
                <span style={{ width: '92%' }} />
                <em>Chicken Biryani</em>
              </div>
              <div className="lp-mockup-bar">
                <span style={{ width: '74%' }} />
                <em>Masala Dosa</em>
              </div>
              <div className="lp-mockup-bar">
                <span style={{ width: '58%' }} />
                <em>Paneer Butter Masala</em>
              </div>
            </div>
            <div className="lp-mockup-card lp-mockup-card-dark">
              <div className="lp-mockup-card-label lp-mockup-card-label-light">P&amp;L · MTD</div>
              <div className="lp-mockup-card-value lp-mockup-card-value-light">28% margin</div>
              <div className="lp-mockup-card-sub">COGS 31% · Labour 18%</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
