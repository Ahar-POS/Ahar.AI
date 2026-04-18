import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './LandingPage.css';
import './MarketingPages.css';

export default function PricingPage() {
  const { isAuthenticated } = useAuth();
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
        <section className="mp-hero" aria-labelledby="pricing-title">
          <div className="lp-container">
            <span className="lp-eyebrow">Pricing</span>
            <h1 id="pricing-title" className="lp-section-title">
              Simple pricing for Indian restaurants.
            </h1>
            <p className="mp-kicker">
              Start free. Upgrade when you’re ready. No per-bill commissions and no surprise add-ons.
            </p>

            <div className="mp-card-grid" aria-label="Pricing plans">
              <div className="mp-card">
                <div className="mp-card-title">Starter</div>
                <div className="mp-card-price">
                  <div className="mp-price-amount">Free</div>
                </div>
                <ul className="mp-card-list">
                  <li>✓ Core POS + basic inventory</li>
                  <li>✓ Daily summaries</li>
                  <li>✓ 1 user</li>
                  <li>✓ Email support</li>
                </ul>
                <div className="mp-card-cta">
                  <Link to={primaryCtaTo} className="lp-btn lp-btn-ghost">
                    {primaryCtaLabel} <span aria-hidden="true">→</span>
                  </Link>
                </div>
              </div>

              <div className="mp-card mp-card-featured">
                <div className="mp-card-title">Growth</div>
                <div className="mp-card-price">
                  <div className="mp-price-amount">Custom</div>
                  <div className="mp-price-period">per outlet / month</div>
                </div>
                <ul className="mp-card-list">
                  <li>✓ Full inventory BOM + expiry tracking</li>
                  <li>✓ Demand forecasting + smart reorder</li>
                  <li>✓ Autonomous agent alerts</li>
                  <li>✓ Priority onboarding</li>
                </ul>
                <div className="mp-card-cta">
                  <Link to={primaryCtaTo} className="lp-btn lp-btn-primary">
                    {primaryCtaLabel} <span aria-hidden="true">→</span>
                  </Link>
                </div>
              </div>

              <div className="mp-card">
                <div className="mp-card-title">Multi-outlet</div>
                <div className="mp-card-price">
                  <div className="mp-price-amount">Let’s talk</div>
                </div>
                <ul className="mp-card-list">
                  <li>✓ Multi-outlet reporting</li>
                  <li>✓ Role-based access</li>
                  <li>✓ Integrations + data exports</li>
                  <li>✓ Dedicated support</li>
                </ul>
                <div className="mp-card-cta">
                  <Link to="/about" className="lp-btn lp-btn-ghost">
                    Contact sales <span aria-hidden="true">→</span>
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mp-section" aria-label="Pricing note">
          <div className="lp-container">
            <div className="mp-two-col">
              <div className="mp-panel">
                <div className="mp-panel-title">What’s included</div>
                <p className="mp-panel-body">
                  POS, inventory, forecasting, agents, and P&amp;L work best when they share one source of truth.
                  Every plan focuses on owner time saved and fewer stock surprises.
                </p>
              </div>
              <div className="mp-panel">
                <div className="mp-panel-title">Need a quote?</div>
                <p className="mp-panel-body">
                  If you’re running multiple outlets or have specific workflows (cloud kitchen, tiffin, QSR),
                  we’ll tailor onboarding and rollout to your operations.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
