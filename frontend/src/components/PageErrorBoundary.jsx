import { Component } from 'react';

/**
 * PageErrorBoundary — reusable boundary that catches render errors in a single
 * page subtree. Shows a Bahasa Indonesia fallback with retry button.
 *
 * Unlike the global ErrorBoundary (which reloads the whole app), this one
 * resets just the page boundary so the rest of the app stays interactive.
 */
export default class PageErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="page-error-boundary">
          <div className="page-error-content">
            <h2>Gagal Memuat Halaman</h2>
            <p className="page-error-message">
              {this.state.error?.message || 'Terjadi kesalahan saat memuat halaman ini.'}
            </p>
            <button className="sort-chip active" onClick={this.handleRetry}>
              Coba Lagi
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
