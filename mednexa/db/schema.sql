PRAGMA foreign_keys = ON;

CREATE TABLE reps (
  rep_id TEXT PRIMARY KEY, name TEXT NOT NULL CHECK (trim(name) <> ''),
  territory TEXT NOT NULL UNIQUE
);
CREATE TABLE doctors (
  doctor_id TEXT PRIMARY KEY, name TEXT NOT NULL CHECK (trim(name) <> ''),
  specialty TEXT NOT NULL, area TEXT NOT NULL,
  territory TEXT NOT NULL REFERENCES reps(territory),
  monthly_prescriptions INTEGER NOT NULL CHECK (monthly_prescriptions >= 0),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE products (product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL UNIQUE);
CREATE TABLE inventory (
  inventory_id TEXT PRIMARY KEY, product_id TEXT NOT NULL UNIQUE REFERENCES products(product_id),
  opening_stock INTEGER NOT NULL CHECK (opening_stock >= 0),
  current_stock INTEGER NOT NULL CHECK (current_stock >= 0),
  minimum_stock INTEGER NOT NULL CHECK (minimum_stock >= 0)
);
CREATE TABLE visits (
  visit_id TEXT PRIMARY KEY, rep_id TEXT NOT NULL REFERENCES reps(rep_id),
  doctor_id TEXT NOT NULL REFERENCES doctors(doctor_id), visit_date TEXT NOT NULL,
  outcome TEXT NULL CHECK (outcome IN ('Positive','Neutral','Negative','Doctor unavailable')),
  notes TEXT NULL, source TEXT NOT NULL CHECK (source IN ('SEED','APP')), created_at TEXT NOT NULL
);
CREATE TABLE visit_products (
  visit_id TEXT NOT NULL REFERENCES visits(visit_id),
  product_id TEXT NOT NULL REFERENCES products(product_id),
  feedback TEXT NULL CHECK (feedback IN ('Positive','Neutral','Negative')),
  PRIMARY KEY (visit_id, product_id)
);
CREATE TABLE sample_transactions (
  transaction_id TEXT PRIMARY KEY, visit_id TEXT NOT NULL REFERENCES visits(visit_id),
  product_id TEXT NOT NULL REFERENCES products(product_id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  transaction_type TEXT NOT NULL CHECK (transaction_type IN ('SAMPLE_ISSUED','SAMPLE_RETURNED')),
  transaction_date TEXT NOT NULL
);
CREATE TABLE follow_ups (
  follow_up_id TEXT PRIMARY KEY, visit_id TEXT NOT NULL UNIQUE REFERENCES visits(visit_id),
  due_date TEXT NOT NULL, notes TEXT NULL,
  status TEXT NOT NULL CHECK (status IN ('Pending','Completed')),
  completed_on TEXT NULL,
  completion_method TEXT NULL CHECK (completion_method IN ('VISIT','CONTACT')),
  completed_visit_id TEXT NULL REFERENCES visits(visit_id),
  completion_note TEXT NULL,
  CHECK (status = 'Pending' OR (completed_on IS NOT NULL AND completion_method IS NOT NULL)),
  CHECK (completion_method IS NULL
         OR (completion_method = 'VISIT' AND completed_visit_id IS NOT NULL)
         OR (completion_method = 'CONTACT' AND trim(coalesce(completion_note,'')) <> ''))
);
CREATE TABLE plan_runs (
  run_id TEXT PRIMARY KEY, rep_id TEXT NOT NULL REFERENCES reps(rep_id),
  start_date TEXT NOT NULL, num_days INTEGER NOT NULL CHECK (num_days > 0),
  as_of TEXT NOT NULL, generated_at TEXT NOT NULL
);
CREATE TABLE plan_items (
  plan_item_id TEXT PRIMARY KEY, rep_id TEXT NOT NULL REFERENCES reps(rep_id),
  doctor_id TEXT NOT NULL REFERENCES doctors(doctor_id),
  planned_date TEXT NOT NULL, original_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('PLANNED','COMPLETED','SKIPPED','CANCELLED')),
  is_manual INTEGER NOT NULL DEFAULT 0 CHECK (is_manual IN (0,1)),
  score REAL NULL, score_breakdown TEXT NULL, reasons TEXT NULL,
  run_id TEXT NULL REFERENCES plan_runs(run_id),
  visit_id TEXT NULL UNIQUE REFERENCES visits(visit_id),
  status_note TEXT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  CHECK (status <> 'COMPLETED' OR visit_id IS NOT NULL)
);
CREATE TABLE plan_item_follow_ups (
  plan_item_id TEXT NOT NULL REFERENCES plan_items(plan_item_id),
  follow_up_id TEXT NOT NULL REFERENCES follow_ups(follow_up_id),
  PRIMARY KEY (plan_item_id, follow_up_id)
);
CREATE TABLE plan_item_events (
  event_id TEXT PRIMARY KEY, plan_item_id TEXT NOT NULL REFERENCES plan_items(plan_item_id),
  from_status TEXT, to_status TEXT, from_date TEXT, to_date TEXT,
  actor TEXT NOT NULL, note TEXT, at TEXT NOT NULL
);
CREATE TABLE actions (
  action_key TEXT PRIMARY KEY,
  source_type TEXT NOT NULL CHECK (source_type IN ('FOLLOW_UP','PLAN_ITEM')),
  source_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('OPEN','SNOOZED','DONE','DISMISSED','RESOLVED')),
  snoozed_until TEXT NULL, first_seen_at TEXT NOT NULL, closed_at TEXT NULL
);
CREATE TABLE action_events (
  event_id TEXT PRIMARY KEY, action_key TEXT NOT NULL REFERENCES actions(action_key),
  from_status TEXT, to_status TEXT NOT NULL, actor TEXT NOT NULL, note TEXT, at TEXT NOT NULL
);

CREATE INDEX ix_visits_doctor ON visits(doctor_id, visit_date);
CREATE INDEX ix_visits_rep ON visits(rep_id, visit_date);
CREATE INDEX ix_tx_product ON sample_transactions(product_id);
CREATE INDEX ix_tx_visit ON sample_transactions(visit_id);
CREATE INDEX ix_fu_status ON follow_ups(status, due_date);
CREATE INDEX ix_plan_rep ON plan_items(rep_id, planned_date);
CREATE INDEX ix_plan_doctor ON plan_items(doctor_id, status);
CREATE INDEX ix_doctors_territory ON doctors(territory);

CREATE VIEW v_visit_samples AS
SELECT v.visit_id,
  COALESCE(SUM(CASE WHEN t.transaction_type='SAMPLE_ISSUED' THEN t.quantity END),0) AS issued,
  COALESCE(SUM(CASE WHEN t.transaction_type='SAMPLE_RETURNED' THEN t.quantity END),0) AS returned,
  COALESCE(SUM(CASE WHEN t.transaction_type='SAMPLE_ISSUED' THEN t.quantity ELSE -t.quantity END),0) AS net
FROM visits v LEFT JOIN sample_transactions t ON t.visit_id = v.visit_id GROUP BY v.visit_id;

CREATE VIEW v_visit_products_text AS
SELECT visit_id, GROUP_CONCAT(product_name, ';') AS products_discussed
FROM (SELECT vp.visit_id, p.product_name FROM visit_products vp JOIN products p USING(product_id)
      ORDER BY vp.visit_id, p.product_name)
GROUP BY visit_id;

CREATE VIEW v_visit_followup AS
SELECT v.visit_id,
  CASE WHEN f.follow_up_id IS NULL THEN 'No' ELSE 'Yes' END AS follow_up_required,
  f.due_date AS follow_up_date,
  COALESCE(f.status, 'Not Required') AS follow_up_status
FROM visits v LEFT JOIN follow_ups f ON f.visit_id = v.visit_id;

CREATE VIEW v_last_visit AS
SELECT doctor_id, MAX(visit_date) AS last_visit_date, COUNT(*) AS visit_count
FROM visits GROUP BY doctor_id;
