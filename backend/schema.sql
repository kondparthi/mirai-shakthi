-- MIRAI Shakthi – Phase 0 schema (MySQL 8+, utf8mb4). Generated from app/models.py.
-- Easiest setup is `python -m seed.seed`, which creates these tables and loads starter data.
CREATE DATABASE IF NOT EXISTS miraishakthi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE miraishakthi;

CREATE TABLE audit_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER, 
	action VARCHAR(60) NOT NULL, 
	entity VARCHAR(60), 
	entity_id INTEGER, 
	detail JSON, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE TABLE intents (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	code VARCHAR(60) NOT NULL, 
	module VARCHAR(20) NOT NULL, 
	title_en VARCHAR(160) NOT NULL, 
	title_te VARCHAR(160), 
	description VARCHAR(500), 
	keywords JSON NOT NULL, 
	sample_questions JSON NOT NULL, 
	connect_service VARCHAR(60), 
	active BOOL NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_intents_module ON intents (module);

CREATE TABLE kb_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	title VARCHAR(255) NOT NULL, 
	module VARCHAR(20) NOT NULL, 
	intent_code VARCHAR(60), 
	language VARCHAR(5) NOT NULL, 
	body TEXT NOT NULL, 
	source_url VARCHAR(300), 
	verified_by VARCHAR(120), 
	verified_on DATE, 
	review_due DATE, 
	status VARCHAR(15) NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE FULLTEXT INDEX ft_kb_title_body ON kb_items (title, body);

CREATE INDEX ix_kb_items_intent_code ON kb_items (intent_code);

CREATE INDEX ix_kb_items_module ON kb_items (module);

CREATE TABLE otp_codes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	mobile VARCHAR(15) NOT NULL, 
	code_hash VARCHAR(255) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	attempts SMALLINT NOT NULL, 
	used BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_otp_codes_mobile ON otp_codes (mobile);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	mobile VARCHAR(15), 
	email VARCHAR(190), 
	name VARCHAR(120), 
	`role` VARCHAR(20) NOT NULL, 
	password_hash VARCHAR(255), 
	language VARCHAR(5) NOT NULL, 
	is_active BOOL NOT NULL, 
	consent_version VARCHAR(20), 
	consent_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	UNIQUE (mobile), 
	UNIQUE (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_users_role ON users (`role`);

CREATE TABLE experts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(160) NOT NULL, 
	organisation VARCHAR(160), 
	expert_type VARCHAR(30) NOT NULL, 
	services JSON NOT NULL, 
	reg_no VARCHAR(60), 
	districts JSON NOT NULL, 
	languages JSON NOT NULL, 
	fee_note VARCHAR(160), 
	response_hours SMALLINT NOT NULL, 
	rating DOUBLE, 
	status VARCHAR(15) NOT NULL, 
	user_id INTEGER, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE guidance_sessions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	module VARCHAR(20), 
	intent_code VARCHAR(60), 
	title VARCHAR(200), 
	current_step SMALLINT NOT NULL, 
	language VARCHAR(5) NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_guidance_sessions_user_id ON guidance_sessions (user_id);

CREATE TABLE msme_profiles (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	owner_name VARCHAR(120), 
	business_name VARCHAR(160), 
	stage VARCHAR(20), 
	business_type VARCHAR(20), 
	sector VARCHAR(60), 
	product VARCHAR(255), 
	district VARCHAR(80), 
	mandal VARCHAR(80), 
	ownership VARCHAR(20), 
	turnover_band SMALLINT, 
	employees INTEGER, 
	registrations JSON NOT NULL, 
	channels JSON NOT NULL, 
	books_kept VARCHAR(20), 
	has_loan BOOL, 
	flags JSON NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE requirement_rules (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	intent_id INTEGER NOT NULL, 
	item_code VARCHAR(60) NOT NULL, 
	title_en VARCHAR(200) NOT NULL, 
	title_te VARCHAR(200), 
	why_en TEXT, 
	why_te TEXT, 
	`condition` JSON, 
	have_check JSON, 
	step_order SMALLINT NOT NULL, 
	documents VARCHAR(500), 
	time_estimate VARCHAR(80), 
	cost_note VARCHAR(160), 
	official_link VARCHAR(300), 
	active BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	FOREIGN KEY(intent_id) REFERENCES intents (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_requirement_rules_intent_id ON requirement_rules (intent_id);

CREATE TABLE connect_requests (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	session_id INTEGER, 
	user_id INTEGER NOT NULL, 
	expert_id INTEGER, 
	service VARCHAR(60) NOT NULL, 
	summary TEXT NOT NULL, 
	preferred_contact VARCHAR(20), 
	budget VARCHAR(30), 
	consent_at DATETIME NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES guidance_sessions (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(expert_id) REFERENCES experts (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_connect_requests_user_id ON connect_requests (user_id);

CREATE INDEX ix_connect_requests_expert_id ON connect_requests (expert_id);

CREATE TABLE guidance_messages (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	session_id INTEGER NOT NULL, 
	`role` VARCHAR(10) NOT NULL, 
	content TEXT NOT NULL, 
	payload JSON, 
	rating SMALLINT, 
	flagged BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES guidance_sessions (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_guidance_messages_session_id ON guidance_messages (session_id);

CREATE TABLE session_gaps (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	session_id INTEGER NOT NULL, 
	item_code VARCHAR(60) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (session_id, item_code), 
	FOREIGN KEY(session_id) REFERENCES guidance_sessions (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Sprint 3
CREATE TABLE artefacts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	session_id INTEGER, 
	kind VARCHAR(20) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	inputs JSON, 
	outputs JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(session_id) REFERENCES guidance_sessions (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_artefacts_kind ON artefacts (kind);

CREATE INDEX ix_artefacts_user_id ON artefacts (user_id);

-- Sprint 4
CREATE TABLE connect_updates (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	request_id INTEGER NOT NULL, 
	author_role VARCHAR(10) NOT NULL, 
	author_id INTEGER, 
	kind VARCHAR(10) NOT NULL, 
	status VARCHAR(15), 
	text TEXT, 
	amount FLOAT, 
	data JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES connect_requests (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_connect_updates_request_id ON connect_updates (request_id);
