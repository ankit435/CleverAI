import React, { useState, useEffect } from 'react';
import { useChatContext } from '../context/ChatContext';
import { apiClient } from '../config/apiClient';
import { X, Lock, Mail, User, LogIn, UserPlus, LogOut, CheckCircle, Eye, EyeOff, Zap, AlertCircle } from 'lucide-react';

declare global {
  interface Window {
    google?: any;
  }
}

interface AuthModalProps {
  isProtectedGate?: boolean;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isProtectedGate = false }) => {
  const {
    isAuthModalOpen,
    setIsAuthModalOpen,
    appConfig,
    userSession,
    loginUser,
    logoutUser
  } = useChatContext();

  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState(() => localStorage.getItem('clever_remember_email') || '');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [rememberMe, setRememberMe] = useState(() => Boolean(localStorage.getItem('clever_remember_email')));
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // Inject official Google Identity Services script
    if (!document.getElementById('google-gsi-script')) {
      const script = document.createElement('script');
      script.id = 'google-gsi-script';
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  }, []);

  if (!isProtectedGate && !isAuthModalOpen) return null;

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !password.trim()) {
      setError('Please enter both email and password.');
      return;
    }

    if (mode === 'signup' && !name.trim()) {
      setError('Please enter your full name for registration.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    setLoading(true);

    try {
      let data: any;
      if (mode === 'signup') {
        data = await apiClient.auth.signup({
          name: name.trim(),
          email: email.trim(),
          password,
          rememberMe
        });
      } else {
        data = await apiClient.auth.login({
          email: email.trim(),
          password,
          rememberMe
        });
      }

      if (rememberMe) {
        localStorage.setItem('clever_remember_email', email.trim());
      } else {
        localStorage.removeItem('clever_remember_email');
      }

      loginUser(data.token, {
        id: data.user?.id,
        name: data.user?.name || name || 'Ankit',
        email: data.user?.email || email,
        avatarUrl: data.user?.avatarUrl || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80',
        plan: data.user?.plan || 'Free'
      });

      setIsAuthModalOpen(false);
    } catch (err: any) {
      setError(err.message || 'Authentication error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSSOClick = async () => {
    setLoading(true);
    setError('');

    try {
      const emailInput = email.trim() || `google_user_${Date.now()}@gmail.com`;
      const nameInput = name.trim() || emailInput.split('@')[0];
      const data = await apiClient.auth.google({
        name: nameInput,
        email: emailInput,
        avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80',
        googleId: `google-sso-${Date.now()}`
      });

      if (rememberMe && data.user?.email) {
        localStorage.setItem('clever_remember_email', data.user.email);
      }

      loginUser(data.token, data.user);
      setIsAuthModalOpen(false);
    } catch (err: any) {
      setError(err.message || 'Google SSO authentication error.');
    } finally {
      setLoading(false);
    }
  };

  const googleBtnStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '10px',
    padding: '12px',
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border-light)',
    fontWeight: 600,
    width: '100%',
    borderRadius: '12px',
    cursor: 'pointer',
    fontSize: '14px',
    transition: 'all 0.2s ease'
  };

  const logoutBtnStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    color: '#ef4444',
    borderColor: '#ef4444',
    marginTop: '10px',
    padding: '10px',
    width: '100%',
    borderRadius: '12px',
    cursor: 'pointer'
  };

  return (
    <div className={isProtectedGate ? 'protected-gate-screen' : 'modal-overlay'} onClick={() => !isProtectedGate && setIsAuthModalOpen(false)}>
      <div className="modal-content" style={{ maxWidth: '440px' }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header" style={{ flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '8px', paddingTop: '24px' }}>
          <div className="logo-badge" style={{ width: '42px', height: '42px', borderRadius: '12px' }}>
            <Zap size={22} fill="currentColor" />
          </div>
          <h2 style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-main)' }}>{appConfig.branding.appName} Workspace</h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            {userSession.isLoggedIn ? 'Manage your active workspace session' : 'Sign in to access your protected AI agent workspace'}
          </p>
        </div>

        <div className="modal-body">
          {/* Active Session Display */}
          {userSession.isLoggedIn ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', alignItems: 'center', padding: '10px 0' }}>
              <div style={{ position: 'relative' }}>
                <img
                  src={userSession.avatarUrl}
                  alt={userSession.name}
                  style={{ width: '64px', height: '64px', borderRadius: '50%', border: '2px solid var(--primary)' }}
                />
                <span
                  style={{
                    position: 'absolute',
                    bottom: '2px',
                    right: '2px',
                    width: '14px',
                    height: '14px',
                    backgroundColor: '#10b981',
                    borderRadius: '50%',
                    border: '2px solid var(--bg-surface)'
                  }}
                />
              </div>

              <div style={{ textAlign: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                  <h4 style={{ fontSize: '17px', fontWeight: 700 }}>{userSession.name}</h4>
                  <CheckCircle size={16} style={{ color: '#10b981' }} />
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>{userSession.email}</p>
                <span className="free-pill" style={{ display: 'inline-block', marginTop: '6px' }}>
                  Active Session ({userSession.plan} Plan)
                </span>
              </div>

              <button
                type="button"
                className="upgrade-btn"
                style={logoutBtnStyle}
                onClick={() => {
                  logoutUser();
                }}
              >
                <LogOut size={16} />
                <span>Log Out of Workspace Session</span>
              </button>
            </div>
          ) : (
            <>
              {/* Google OAuth SSO Button */}
              <button
                type="button"
                className="upgrade-btn"
                style={googleBtnStyle}
                onClick={handleGoogleSSOClick}
                disabled={loading}
              >
                <svg width="18" height="18" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                </svg>
                <span>{loading ? 'Authenticating with Google...' : 'Continue with Google'}</span>
              </button>

              <div style={{ display: 'flex', alignItems: 'center', margin: '16px 0', gap: '10px' }}>
                <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-light)' }} />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>OR EMAIL</span>
                <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-light)' }} />
              </div>

              {/* Error Alert Banner */}
              {error && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', borderRadius: '8px', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', fontSize: '13px', fontWeight: 500, marginBottom: '12px' }}>
                  <AlertCircle size={16} style={{ flexShrink: 0 }} />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleEmailAuth} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {mode === 'signup' && (
                  <div>
                    <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Full Name</label>
                    <div className="search-input-wrapper" style={{ marginTop: '4px' }}>
                      <User size={15} />
                      <input
                        type="text"
                        required
                        placeholder="Ankit"
                        className="search-input"
                        value={name}
                        onChange={e => setName(e.target.value)}
                      />
                    </div>
                  </div>
                )}

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Email Address</label>
                  <div className="search-input-wrapper" style={{ marginTop: '4px' }}>
                    <Mail size={15} />
                    <input
                      type="email"
                      required
                      placeholder="name@example.com"
                      className="search-input"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Password</label>
                  <div className="search-input-wrapper" style={{ marginTop: '4px', position: 'relative' }}>
                    <Lock size={15} />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      required
                      placeholder="••••••••"
                      className="search-input"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0 4px' }}
                    >
                      {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                {/* Remember Me Checkbox */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '2px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={e => setRememberMe(e.target.checked)}
                      style={{ accentColor: 'var(--primary)', width: '15px', height: '15px', borderRadius: '4px' }}
                    />
                    <span>Remember me on this device</span>
                  </label>
                </div>

                <button
                  type="submit"
                  className="btn-new-chat"
                  style={{ justifyContent: 'center', padding: '12px', marginTop: '8px', fontSize: '14px' }}
                  disabled={loading}
                >
                  {mode === 'login' ? <LogIn size={16} /> : <UserPlus size={16} />}
                  <span>{loading ? 'Authenticating...' : mode === 'login' ? 'Sign In to Workspace' : 'Create Account'}</span>
                </button>
              </form>

              <div style={{ textAlign: 'center', marginTop: '16px', fontSize: '13px', color: 'var(--text-muted)' }}>
                {mode === 'login' ? "Don't have an account? " : "Already have an account? "}
                <button
                  type="button"
                  style={{ background: 'none', border: 'none', color: 'var(--primary)', fontWeight: 600, cursor: 'pointer' }}
                  onClick={() => {
                    setError('');
                    setMode(mode === 'login' ? 'signup' : 'login');
                  }}
                >
                  {mode === 'login' ? 'Sign up' : 'Log in'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
