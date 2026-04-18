import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './LandingPage.css';
import './MarketingPages.css';

export default function AboutPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="lp-root">
      <header className="lp-nav">
        <div className="lp-container lp-nav-inner">
          <Link to="/" className="lp-brand" aria-label="Ahar.AI home">
            <span className="lp-brand-mark" aria-hidden="true">A</span>
            <span className="lp-brand-text">Ahar<span className="lp-brand-dot">.</span>AI</span>
          </Link>
          <nav className="lp-nav-links" aria-label="Primary">
            <a href="/#capabilities">Product</a>
            <a href="/#how">How it works</a>
            <a href="/#india">For India</a>
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

      <main className="mp-main">
        <section className="mp-hero" aria-labelledby="about-title">
          <div className="lp-container">
            <span className="lp-eyebrow">About</span>
            <h1 id="about-title" className="lp-section-title">
              Built in India, for the reality of Indian kitchens.
            </h1>
            <p className="mp-kicker">
              Ahar.AI is an AI-powered restaurant back office that helps owners run tighter operations:
              inventory that matches the recipe, forecasts that respect festivals, and agents that surface
              what needs action—without drowning you in dashboards.
            </p>
          </div>
        </section>

        <section className="mp-section" aria-label="Our principles">
          <div className="lp-container">
            <div className="mp-two-col">
              <div className="mp-panel">
                <div className="mp-panel-title">Owner time is sacred</div>
                <p className="mp-panel-body">
                  The product is designed around approvals and exceptions—so you spend your day deciding,
                  not chasing stock numbers or reconciling spreadsheets.
                </p>
              </div>
              <div className="mp-panel">
                <div className="mp-panel-title">Truth lives in the BOM</div>
                <p className="mp-panel-body">
                  Inventory and profitability only work when they’re grounded in recipes and batch life.
                  We treat recipe BOM and shelf-life as first-class citizens, not add-ons.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="mp-section" aria-label="Call to action">
          <div className="lp-container" style={{ textAlign: 'center' }}>
            <h2 className="lp-section-title" style={{ fontSize: 'clamp(1.6rem, 3.4vw, 2.4rem)' }}>
              Want to see the Command Center?
            </h2>
            <p className="mp-kicker" style={{ marginLeft: 'auto', marginRight: 'auto' }}>
              Start free, or talk to the team if you have multi-outlet workflows.
            </p>
            <div style={{ marginTop: 22, display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
              <Link to={isAuthenticated ? '/home' : '/signup'} className="lp-btn lp-btn-primary">
                {isAuthenticated ? 'Go to dashboard' : 'Start free trial'} <span aria-hidden="true">→</span>
              </Link>
              <Link to="/pricing" className="lp-btn lp-btn-ghost">
                See pricing <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
