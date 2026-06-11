import { Component } from 'react';

/**
 * ErrorBoundary — catches render errors in its subtree and shows a fallback UI
 * with a retry button. Wraps the entire app to prevent a full white screen crash.
 *
 * Props:
 *   @param {React.ReactNode} children — child tree to catch errors from
 *
 * State:
 *   hasError {boolean} — true after a render error is caught
 *   error   {Error|null} — the caught error object
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-boundary-content">
            <h2>Terjadi Kesalahan</h2>
            <p className="error-boundary-message">
              {this.state.error?.message || 'Aplikasi mengalami error yang tidak terduga.'}
            </p>
            <button
              className="sort-chip active"
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
            >
              Muat Ulang
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
