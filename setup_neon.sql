CREATE TABLE IF NOT EXISTS signal_recommendations (
  id SERIAL PRIMARY KEY,
  symbol TEXT NOT NULL,
  name TEXT,
  recommendation TEXT NOT NULL,
  strength REAL NOT NULL,
  price REAL,
  volume INTEGER,
  avg_volume INTEGER,
  potential_score REAL,
  reasons_json TEXT,
  created_at TEXT NOT NULL,
  evaluated_at TEXT,
  future_price REAL,
  return_pct REAL,
  outcome TEXT,
  is_correct INTEGER,
  learning_adjustment REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_signal_rec_created_at ON signal_recommendations(created_at);
CREATE INDEX IF NOT EXISTS idx_signal_rec_symbol ON signal_recommendations(symbol);
CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_rec_daily ON signal_recommendations(symbol, recommendation, substr(created_at, 1, 10));

CREATE TABLE IF NOT EXISTS virtual_portfolio (
  id SERIAL PRIMARY KEY,
  symbol TEXT NOT NULL UNIQUE,
  qty REAL NOT NULL,
  avg_price REAL NOT NULL,
  target_price REAL,
  stop_loss REAL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_virtual_portfolio_symbol ON virtual_portfolio(symbol);
