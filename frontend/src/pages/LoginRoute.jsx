import { memo, Suspense, lazy } from 'react';
import Skeleton from '../components/Skeleton';
import PageErrorBoundary from '../components/PageErrorBoundary';

const LoginPage = lazy(() => import('../components/LoginPage'));

const fallback = (
  <div className="page page-enter" style={{ padding: '40px 16px' }}>
    <Skeleton variant="card" count={3} />
  </div>
);

/**
 * LoginRoute — Entry untuk user yang belum terautentikasi.
 */
function LoginRoute() {
  return (
    <PageErrorBoundary>
      <Suspense fallback={fallback}>
        <LoginPage />
      </Suspense>
    </PageErrorBoundary>
  );
}

export default memo(LoginRoute);
