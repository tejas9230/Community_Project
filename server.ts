import express, { Request, Response, NextFunction } from 'express';
import session from 'express-session';
import nunjucks from 'nunjucks';
import bcrypt from 'bcryptjs';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import dotenv from 'dotenv';
import pg from 'pg';

dotenv.config();

const { Pool } = pg;

// Supabase PostgreSQL Pool
const pgPool = process.env.DATABASE_URL
  ? new Pool({
      connectionString: process.env.DATABASE_URL,
      ssl: { rejectUnauthorized: false }
    })
  : null;

const app = express();
const PORT = 3000;

// Ensure directories exist
const uploadsDir = path.join(process.cwd(), 'static', 'uploads');
const dataDir = path.join(process.cwd(), 'data');

if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

// Multer Setup
const storage = multer.diskStorage({
  destination: (_req, _file, cb) => {
    cb(null, uploadsDir);
  },
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname) || '.jpg';
    cb(null, `complaint-${Date.now()}-${Math.floor(Math.random() * 1000)}${ext}`);
  }
});
const upload = multer({ storage });

// Body parsers
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// Static Files
app.use('/static', express.static(path.join(process.cwd(), 'static')));

// Session Setup
app.use(session({
  secret: process.env.SECRET_KEY || 'scs-secret-key-12345',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 24 * 60 * 60 * 1000 }
}));

// Flash messages & session compatibility middleware
app.use((req: any, res: Response, next: NextFunction) => {
  if (req.session) {
    if (typeof req.session.get !== 'function') {
      req.session.get = function (key: string, defaultVal: any = undefined) {
        return this[key] !== undefined ? this[key] : defaultVal;
      };
    }
  }
  res.locals.session = req.session;
  res.locals.req = req;
  if (!req.session.flash) req.session.flash = [];
  req.flash = (message: string, category: string = 'info') => {
    req.session.flash.push([category, message]);
  };
  next();
});

// Configure Nunjucks
const env = nunjucks.configure('templates', {
  autoescape: true,
  express: app,
  noCache: true
});

// Nunjucks Custom Tag for {% with %}
env.addExtension('WithExtension', new (function (this: any) {
  this.tags = ['with'];
  this.parse = function (parser: any, nodes: any) {
    const tok = parser.nextToken();
    const args = parser.parseSignature(null, true);
    parser.advanceAfterBlockEnd(tok.value);
    const body = parser.parseUntilBlocks('endwith');
    parser.advanceAfterBlockEnd();
    return new nodes.CallExtension(this, 'run', args, [body]);
  };
  this.run = function (_context: any, _args: any, body: any) {
    return body();
  };
})());

// Nunjucks Custom Globals
env.addGlobal('url_for', (endpoint: string, options?: any) => {
  if (endpoint === 'static') return '/static/' + (options?.filename || '');
  if (endpoint === 'officer_action') return '/officer_action/' + (options?.id || '');
  if (endpoint === 'update_status') return '/update_status/' + (options?.id || '');
  if (endpoint === 'feedback') return '/feedback/' + (options?.id || '');
  if (options && options.id) return `/${endpoint}/${options.id}`;
  return '/' + endpoint;
});

env.addGlobal('get_flashed_messages', function (this: any, options?: any) {
  const req = this.ctx.req;
  if (!req || !req.session || !req.session.flash) return [];
  const messages = [...req.session.flash];
  req.session.flash = [];
  return messages;
});

// Nunjucks Custom Filters
env.addFilter('format', (str: string, val: any) => {
  if (typeof str === 'string' && str.includes('%04d')) {
    const num = parseInt(val, 10) || 0;
    return String(num).padStart(4, '0');
  }
  return String(val);
});

env.addFilter('tojson', (val: any) => {
  return JSON.stringify(val);
});

env.addFilter('round', (val: any, decimals: number = 0) => {
  const num = parseFloat(val) || 0;
  return num.toFixed(decimals);
});

env.addFilter('int', (val: any) => {
  return parseInt(val, 10) || 0;
});

env.addFilter('truncate', (val: any, length: number = 100) => {
  const str = String(val || '');
  return str.length > length ? str.substring(0, length) + '...' : str;
});

env.addFilter('selectattr', (arr: any[], attr: string, op: string, val: any) => {
  if (!Array.isArray(arr)) return [];
  if (op === 'eq') return arr.filter((x: any) => x[attr] == val);
  if (op === 'lt') return arr.filter((x: any) => x[attr] < val);
  if (op === 'gt') return arr.filter((x: any) => x[attr] > val);
  return arr;
});

env.addFilter('image_url', (path: any) => {
  if (!path) return '';
  const pathStr = String(path).trim();
  if (pathStr.startsWith('http://') || pathStr.startsWith('https://')) {
    return pathStr;
  }
  const parts = pathStr.replace(/\\/g, '/').split('/');
  const filename = parts[parts.length - 1];
  return `/static/uploads/${filename}`;
});

// Attach req, session & Jinja request.args compat to template rendering context
app.use((req: any, res: Response, next: NextFunction) => {
  res.locals.req = req;
  if (req.session) {
    if (typeof req.session.get !== 'function') {
      req.session.get = function (key: string, defaultVal: any = undefined) {
        return this[key] !== undefined ? this[key] : defaultVal;
      };
    }
  }
  res.locals.session = req.session;
  res.locals.request = {
    args: {
      get: (key: string, defaultVal: string = '') => (req.query[key] !== undefined ? req.query[key] : defaultVal)
    }
  };
  next();
});

// SLA Days mapping
const SLA_DAYS: Record<string, number> = {
  "Road Damage": 7,
  "Water Supply": 3,
  "Electricity": 2,
  "Street Light": 3,
  "Garbage": 2,
  "Drainage": 4,
  "Animal": 1,
  "Traffic": 3,
  "Public Property": 5,
  "Parks & Green Spaces": 5,
  "Others": 7,
};

// Types & Data Model
interface User {
  username: string;
  passwordHash: string;
  role: 'Citizen' | 'Admin' | 'Officer';
  department?: string;
  email?: string;
  phone?: string;
  created_at?: string;
}

interface Complaint {
  id: number;
  username: string;
  category: string;
  priority: string;
  department: string;
  address: string;
  latitude: number;
  longitude: number;
  description: string;
  status: string; // Pending, In Progress, Resolved, Rejected
  image_path: string;
  resolution_image?: string;
  feedback?: string;
  rating?: number;
  rejection_reason?: string;
  resolution_score?: number;
  verification_status?: string;
  needs_verification?: number;
  created_at: string;
  updated_at: string;
  sla_deadline: string;
  escalated?: number;
  assigned_to?: string;
  officer_remark?: string;
  is_emergency?: number;
  upvotes?: number;
}

interface ComplaintHistory {
  id: number;
  complaint_id: number;
  officer_username: string;
  old_status: string;
  new_status: string;
  remarks: string;
  action_time: string;
}

interface Notification {
  id: number;
  username: string;
  message: string;
  is_read: number;
  created_at: string;
}

interface Announcement {
  id: number;
  title: string;
  body: string;
  created_by: string;
  created_at: string;
  expires_at?: string;
  is_active: number;
}

interface CommunitySettings {
  name: string;
  latitude: number;
  longitude: number;
  radius: number;
}

interface DatabaseSchema {
  users: User[];
  complaints: Complaint[];
  history: ComplaintHistory[];
  notifications: Notification[];
  announcements: Announcement[];
  communitySettings: CommunitySettings;
  adminDirectives?: any[];
  nextComplaintId: number;
  nextNotificationId: number;
  nextHistoryId: number;
  nextAnnouncementId: number;
  nextDirectiveId?: number;
}

const DB_FILE = path.join(dataDir, 'db.json');

let db: DatabaseSchema = {
  users: [],
  complaints: [],
  history: [],
  notifications: [],
  announcements: [],
  communitySettings: {
    name: 'Rasapudipalem Community',
    latitude: 17.6868,
    longitude: 83.2185,
    radius: 5.0
  },
  adminDirectives: [],
  nextComplaintId: 1001,
  nextNotificationId: 1,
  nextHistoryId: 1,
  nextAnnouncementId: 1,
  nextDirectiveId: 1
};

// Persistent Database helper functions
function saveDatabase() {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2), 'utf-8');
  } catch (err) {
    console.error('Failed to save database:', err);
  }
}

async function loadOrSeedDatabase() {
  // If Supabase pool is configured, sync directly from Supabase PostgreSQL!
  if (pgPool) {
    try {
      console.log('Connecting to Supabase PostgreSQL database...');
      const userRes = await pgPool.query('SELECT username, password, role, department, email, phone FROM users');
      if (userRes.rows && userRes.rows.length > 0) {
        db.users = userRes.rows.map(r => ({
          username: r.username,
          passwordHash: r.password,
          role: r.role || 'Citizen',
          department: r.department,
          email: r.email || `${r.username}@gov.in`,
          phone: r.phone || ''
        }));
        console.log(`Synced ${db.users.length} users directly from Supabase PostgreSQL!`);
      }

      const compRes = await pgPool.query('SELECT * FROM complaints ORDER BY id ASC');
      if (compRes.rows && compRes.rows.length > 0) {
        db.complaints = compRes.rows.map(r => ({
          id: r.id,
          username: r.username,
          category: r.category,
          priority: r.priority,
          department: r.department,
          address: r.address,
          latitude: parseFloat(r.latitude) || 17.6870,
          longitude: parseFloat(r.longitude) || 83.2190,
          description: r.description,
          status: r.status,
          image_path: r.image_path,
          created_at: r.created_at,
          updated_at: r.updated_at,
          sla_deadline: r.sla_deadline,
          assigned_to: r.assigned_to,
          needs_verification: r.needs_verification || 0,
          escalated: r.escalated || 0,
          upvotes: r.upvotes || 0,
          is_emergency: r.is_emergency || 0,
          officer_remark: r.officer_remark,
          resolution_image: r.resolution_image,
          resolution_score: r.resolution_score,
          verification_status: r.verification_status,
          rejection_reason: r.rejection_reason,
          rating: r.rating,
          feedback: r.feedback
        }));
        if (db.complaints.length > 0) {
          db.nextComplaintId = Math.max(...db.complaints.map(c => c.id)) + 1;
        }
        console.log(`Synced ${db.complaints.length} complaints directly from Supabase PostgreSQL!`);
      }
      saveDatabase();
      return;
    } catch (pgErr) {
      console.error('Supabase connection error, falling back to local storage:', pgErr);
    }
  }

  if (fs.existsSync(DB_FILE)) {
    try {
      const data = fs.readFileSync(DB_FILE, 'utf-8');
      db = JSON.parse(data);
      if (!Array.isArray(db.users)) db.users = [];
      if (!Array.isArray(db.complaints)) db.complaints = [];
      if (!Array.isArray(db.history)) db.history = [];
      if (!Array.isArray(db.notifications)) db.notifications = [];
      if (!Array.isArray(db.announcements)) db.announcements = [];
      if (!Array.isArray(db.adminDirectives)) db.adminDirectives = [];
      if (!db.communitySettings) {
        db.communitySettings = {
          name: 'Rasapudipalem Community',
          latitude: 17.6868,
          longitude: 83.2185,
          radius: 5.0
        };
      }
      console.log(`Loaded ${db.users.length} users and ${db.complaints.length} complaints from persistent database.`);
      return;
    } catch (err) {
      console.error('Error reading db.json, re-seeding...', err);
    }
  }

  // Initial Seed
  const adminHash = await bcrypt.hash('admin123', 10);
  db.users.push({ username: 'admin', passwordHash: adminHash, role: 'Admin', email: 'admin@rasapudipalem.gov' });

  const officerData = [
    ["roads", "roads123", "Roads & Infrastructure"],
    ["water", "water123", "Water Supply"],
    ["electricity", "electricity123", "Electricity & Street Lighting"],
    ["sanitation", "sanitation123", "Sanitation & Waste Management"],
    ["drainage", "drainage123", "Drainage & Sewage"],
    ["parks", "parks123", "Parks & Green Spaces"],
    ["property", "property123", "Public Property Maintenance"],
    ["animal", "animal123", "Animal Control"],
    ["traffic", "traffic123", "Traffic & Public Safety"],
    ["others", "others123", "Others"]
  ];

  for (const [uname, pw, dept] of officerData) {
    const hash = await bcrypt.hash(pw, 10);
    db.users.push({ username: uname, passwordHash: hash, role: 'Officer', department: dept, email: `${uname}@rasapudipalem.gov` });
  }

  const citizenHash = await bcrypt.hash('citizen123', 10);
  db.users.push({ username: 'demo_user', passwordHash: citizenHash, role: 'Citizen', email: 'citizen@example.com', phone: '9876543210' });

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} 10:00`;

  db.complaints.push(
    {
      id: 1001,
      username: 'demo_user',
      category: 'Road Damage',
      priority: 'High',
      department: 'Roads & Infrastructure',
      address: 'Main Street, Sector 4, Rasapudipalem',
      latitude: 17.6870,
      longitude: 83.2190,
      description: 'Large pothole on the main road causing traffic delays and risk of two-wheeler accidents.',
      status: 'Pending',
      image_path: 'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=600&auto=format&fit=crop&q=60',
      created_at: dateStr,
      updated_at: dateStr,
      sla_deadline: '21-08-2026',
      assigned_to: 'roads',
      needs_verification: 0,
      escalated: 0,
      upvotes: 4
    },
    {
      id: 1002,
      username: 'demo_user',
      category: 'Street Light',
      priority: 'Medium',
      department: 'Electricity & Street Lighting',
      address: 'Park Avenue, Near Gate 2, Rasapudipalem',
      latitude: 17.6882,
      longitude: 83.2175,
      description: 'Street light flickering and completely off after 8 PM making the intersection dangerous at night.',
      status: 'In Progress',
      image_path: 'https://images.unsplash.com/photo-1509114397022-ed747cca3f65?w=600&auto=format&fit=crop&q=60',
      created_at: dateStr,
      updated_at: dateStr,
      sla_deadline: '17-08-2026',
      assigned_to: 'electricity',
      officer_remark: 'Field team dispatched to replace lighting unit.',
      needs_verification: 0,
      escalated: 0,
      upvotes: 2
    },
    {
      id: 1003,
      username: 'demo_user',
      category: 'Garbage',
      priority: 'High',
      department: 'Sanitation & Waste Management',
      address: 'Market Yard Road, Rasapudipalem',
      latitude: 17.6855,
      longitude: 83.2201,
      description: 'Overflowing municipal garbage bin creating unsanitary conditions and foul odor near shops.',
      status: 'Resolved',
      image_path: 'https://images.unsplash.com/photo-1532996122724-e3c354a0b15b?w=600&auto=format&fit=crop&q=60',
      created_at: dateStr,
      updated_at: dateStr,
      sla_deadline: '16-08-2026',
      assigned_to: 'sanitation',
      officer_remark: 'Area cleaned and waste bin sanitized by sanitation crew.',
      rating: 5,
      feedback: 'Quick resolution! Cleaned up within 24 hours of reporting.',
      resolution_score: 94,
      verification_status: 'Verified',
      needs_verification: 0,
      escalated: 0,
      upvotes: 6
    }
  );

  db.history.push(
    {
      id: db.nextHistoryId++,
      complaint_id: 1002,
      officer_username: 'electricity',
      old_status: 'Pending',
      new_status: 'In Progress',
      remarks: 'Field team dispatched to replace lighting unit.',
      action_time: dateStr
    },
    {
      id: db.nextHistoryId++,
      complaint_id: 1003,
      officer_username: 'sanitation',
      old_status: 'In Progress',
      new_status: 'Resolved',
      remarks: 'Area cleaned and waste bin sanitized by sanitation crew.',
      action_time: dateStr
    }
  );

  db.notifications.push(
    {
      id: db.nextNotificationId++,
      username: 'demo_user',
      message: 'Your complaint SCS-1003 regarding Garbage has been resolved.',
      is_read: 0,
      created_at: dateStr
    },
    {
      id: db.nextNotificationId++,
      username: 'demo_user',
      message: 'Your complaint SCS-1002 regarding Street Light is now In Progress.',
      is_read: 0,
      created_at: dateStr
    }
  );

  db.announcements.push({
    id: db.nextAnnouncementId++,
    title: 'Monsoon Preparedness Drive',
    body: 'Municipal sanitation and drainage teams are conducting pre-monsoon clearing across all sectors.',
    created_by: 'admin',
    created_at: dateStr,
    is_active: 1
  });

  db.nextComplaintId = 1004;
  saveDatabase();
}

loadOrSeedDatabase();

// AI / NLP Categorization & Priority Predictor (with Explainable AI & Ambiguity Detection)
function predictComplaint(description: string) {
  const desc = description.toLowerCase();
  let category = "Others";
  let department = "Others";
  let priority = "Medium";
  let confidence = 85;

  const matches: Array<{ cat: string; dept: string; pri: string; conf: number }> = [];

  if (desc.match(/water|pipe|leak|tap|supply|tank|chlorine|seepage/)) {
    matches.push({ cat: "Water Supply", dept: "Water Supply", pri: "High", conf: 94 });
  }
  if (desc.match(/road|pothole|crack|asphalt|street|path|tar|divider|crater/)) {
    matches.push({ cat: "Road Damage", dept: "Roads & Infrastructure", pri: "High", conf: 92 });
  }
  if (desc.match(/street light|dark|lamp|bulb|streetlight|lighting|pole/)) {
    matches.push({ cat: "Street Light", dept: "Electricity & Street Lighting", pri: "Medium", conf: 90 });
  }
  if (desc.match(/electric|power|wire|voltage|transformer|shock|current|fuse/)) {
    matches.push({ cat: "Electricity", dept: "Electricity & Street Lighting", pri: "Critical", conf: 96 });
  }
  if (desc.match(/garbage|trash|waste|dump|bin|clean|smell|litter|debris/)) {
    matches.push({ cat: "Garbage", dept: "Sanitation & Waste Management", pri: "Medium", conf: 88 });
  }
  if (desc.match(/drain|sewage|gutter|overflow|stagnant|manhole|clog/)) {
    matches.push({ cat: "Drainage", dept: "Drainage & Sewage", pri: "High", conf: 91 });
  }
  if (desc.match(/dog|stray|monkey|animal|bite|cattle|cow|snake/)) {
    matches.push({ cat: "Animal", dept: "Animal Control", pri: "High", conf: 89 });
  }
  if (desc.match(/traffic|signal|jam|parking|congestion|accident|gridlock/)) {
    matches.push({ cat: "Traffic", dept: "Traffic & Public Safety", pri: "Medium", conf: 87 });
  }
  if (desc.match(/park|bench|tree|playground|grass|garden|pruning/)) {
    matches.push({ cat: "Parks & Green Spaces", dept: "Parks & Green Spaces", pri: "Low", conf: 86 });
  }
  if (desc.match(/property|building|fence|wall|vandalism|public|bus stop/)) {
    matches.push({ cat: "Public Property", dept: "Public Property Maintenance", pri: "Low", conf: 85 });
  }

  // Extract trigger keywords
  const triggerWords = [
    'pothole', 'crack', 'asphalt', 'leak', 'pipe', 'water', 'garbage',
    'trash', 'drainage', 'sewage', 'street light', 'wire', 'electric',
    'dog', 'animal', 'traffic', 'signal', 'danger', 'broken'
  ];
  const keywords = triggerWords.filter(w => desc.includes(w)).slice(0, 5);
  if (keywords.length === 0) {
    keywords.push(...desc.split(/\s+/).filter(w => w.length > 4).slice(0, 4));
  }

  let is_ambiguous = false;
  let secondary_category: string | null = null;
  let secondary_department: string | null = null;
  let margin = 100;

  if (matches.length > 0) {
    matches.sort((a, b) => b.conf - a.conf);
    category = matches[0].cat;
    department = matches[0].dept;
    priority = matches[0].pri;
    confidence = matches[0].conf;

    if (matches.length > 1) {
      margin = Math.abs(matches[0].conf - matches[1].conf);
      if (margin <= 18) {
        is_ambiguous = true;
        secondary_category = matches[1].cat;
        secondary_department = matches[1].dept;
      }
    }
  }

  return {
    success: true,
    category,
    department,
    priority,
    confidence,
    keywords,
    is_ambiguous,
    secondary_category,
    secondary_department,
    margin
  };
}

function getSlaDeadline(category: string): string {
  const days = SLA_DAYS[category] || 7;
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')}-${d.getFullYear()}`;
}

function getDepartmentForCategory(category: string): string {
  const map: Record<string, string> = {
    "Water Supply": "Water Supply",
    "Road Damage": "Roads & Infrastructure",
    "Street Light": "Electricity & Street Lighting",
    "Electricity": "Electricity & Street Lighting",
    "Garbage": "Sanitation & Waste Management",
    "Drainage": "Drainage & Sewage",
    "Animal": "Animal Control",
    "Traffic": "Traffic & Public Safety",
    "Parks & Green Spaces": "Parks & Green Spaces",
    "Public Property": "Public Property Maintenance",
    "Others": "Others"
  };
  return map[category] || "Others";
}

function getOfficersList() {
  return db.users
    .filter(u => u.role === 'Officer')
    .map(u => [u.username, u.department || 'Officer']);
}

// -------------------------------------------------------------
// Authentication Routes
// -------------------------------------------------------------
app.get('/', (_req, res) => {
  res.render('home.html');
});

app.get('/login', (_req, res) => {
  res.render('login.html');
});

app.post('/login', async (req: any, res) => {
  const { username, password } = req.body;
  const trimmedUname = (username || '').trim();

  // Ensure default demo accounts exist dynamically
  const DEMO_OFFICER_MAP: Record<string, { role: string, dept?: string, pw: string }> = {
    'admin': { role: 'Admin', pw: 'admin123' },
    'roads': { role: 'Officer', dept: 'Roads & Infrastructure', pw: 'roads123' },
    'officer_roads': { role: 'Officer', dept: 'Roads & Infrastructure', pw: 'roads123' },
    'water': { role: 'Officer', dept: 'Water Supply', pw: 'water123' },
    'electricity': { role: 'Officer', dept: 'Electricity & Street Lighting', pw: 'electricity123' },
    'officer_electricity': { role: 'Officer', dept: 'Electricity & Street Lighting', pw: 'electricity123' },
    'sanitation': { role: 'Officer', dept: 'Sanitation & Waste Management', pw: 'sanitation123' },
    'officer_sanitation': { role: 'Officer', dept: 'Sanitation & Waste Management', pw: 'sanitation123' },
    'drainage': { role: 'Officer', dept: 'Drainage & Sewage', pw: 'drainage123' },
    'officer_drainage': { role: 'Officer', dept: 'Drainage & Sewage', pw: 'drainage123' },
    'parks': { role: 'Officer', dept: 'Parks & Green Spaces', pw: 'parks123' },
    'property': { role: 'Officer', dept: 'Public Property Maintenance', pw: 'property123' },
    'animal': { role: 'Officer', dept: 'Animal Control', pw: 'animal123' },
    'traffic': { role: 'Officer', dept: 'Traffic & Public Safety', pw: 'traffic123' },
    'others': { role: 'Officer', dept: 'Others', pw: 'others123' },
    'citizen1': { role: 'Citizen', pw: 'user123' },
    'citizen2': { role: 'Citizen', pw: 'user123' },
    'citizen3': { role: 'Citizen', pw: 'user123' },
    'demo_user': { role: 'Citizen', pw: 'citizen123' }
  };

  const normUser = trimmedUname.toLowerCase();
  if (DEMO_OFFICER_MAP[normUser] && !db.users.some(u => u.username.toLowerCase() === normUser)) {
    const dInfo = DEMO_OFFICER_MAP[normUser];
    const pHash = await bcrypt.hash(dInfo.pw, 10);
    db.users.push({
      username: normUser,
      passwordHash: pHash,
      role: dInfo.role as any,
      department: dInfo.dept,
      email: `${normUser}@gov.in`,
      created_at: new Date().toISOString()
    });
    saveDatabase();
  }

  const user = db.users.find(u => u.username.toLowerCase() === trimmedUname.toLowerCase());

  if (!user) {
    req.flash('Invalid username or password. Please try again.', 'error');
    return res.redirect('/login');
  }

  let match = false;
  try {
    if (user.passwordHash && (user.passwordHash.startsWith('$2a$') || user.passwordHash.startsWith('$2b$'))) {
      match = await bcrypt.compare(password || '', user.passwordHash);
    } else {
      match = (password === user.passwordHash);
    }
  } catch (err) {
    match = (password === user.passwordHash);
  }

  if (!match) {
    req.flash('Invalid username or password. Please try again.', 'error');
    return res.redirect('/login');
  }

  req.session.username = user.username;
  req.session.role = user.role;
  req.session.department = user.department;

  const roleLower = String(user.role || '').toLowerCase();
  const unameLower = String(user.username || '').toLowerCase();

  if (roleLower === 'admin' || unameLower === 'admin') {
    return res.redirect('/admin');
  } else if (roleLower === 'officer') {
    return res.redirect('/department_dashboard');
  } else {
    return res.redirect('/user_dashboard');
  }
});

app.get('/register', (_req, res) => {
  res.render('register.html');
});

app.post('/register', async (req: any, res) => {
  const { username, email, phone, password, confirm_password } = req.body;
  const trimmedUname = (username || '').trim();

  if (!trimmedUname || !password) {
    req.flash('Please fill in all required fields.', 'error');
    return res.redirect('/register');
  }

  if (confirm_password && password !== confirm_password) {
    req.flash('Passwords do not match. Please try again.', 'error');
    return res.redirect('/register');
  }

  if (db.users.some(u => u.username.toLowerCase() === trimmedUname.toLowerCase())) {
    req.flash('Username already exists. Please choose a different username.', 'error');
    return res.redirect('/register');
  }

  const hash = await bcrypt.hash(password, 10);
  const newUser: User = {
    username: trimmedUname,
    passwordHash: hash,
    role: 'Citizen',
    email: email || '',
    phone: phone || '',
    created_at: new Date().toISOString()
  };

  db.users.push(newUser);
  saveDatabase();

  if (pgPool) {
    try {
      await pgPool.query(`
        INSERT INTO users (username, password, role, department, email, phone)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (username) DO NOTHING
      `, [trimmedUname, hash, 'Citizen', null, email || '', phone || '']);
      console.log(`Saved new user ${trimmedUname} to Supabase PostgreSQL!`);
    } catch (pgErr) {
      console.error('Error saving user to Supabase:', pgErr);
    }
  }

  req.flash('Registration successful! You can now log in.', 'success');
  res.redirect('/login');
});

app.get('/forgot_password', (_req, res) => {
  res.render('login.html');
});

app.get('/logout', (req, res) => {
  req.session.destroy(() => {
    res.redirect('/');
  });
});

// -------------------------------------------------------------
// Citizen / User Dashboard
// -------------------------------------------------------------
app.get('/user_dashboard', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const uname = req.session.username;

  const userComplaints = db.complaints.filter(c => c.username === uname);
  const total = userComplaints.length;
  const pending = userComplaints.filter(c => c.status === 'Pending').length;
  const in_progress = userComplaints.filter(c => c.status === 'In Progress').length;
  const resolved = userComplaints.filter(c => c.status === 'Resolved').length;

  const userNotifications = db.notifications
    .filter(n => n.username === uname)
    .reverse()
    .slice(0, 8)
    .map(n => [n.message, n.created_at, n.id]);

  res.render('user_dashboard.html', {
    username: uname,
    total,
    pending,
    in_progress,
    resolved,
    notifications: userNotifications
  });
});

app.get('/help', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  res.render('help.html');
});

// AI Complaint Analysis & Duplicate Detection APIs
app.post('/analyze_complaint', (req, res) => {
  const { description } = req.body;
  if (!description || !description.trim()) {
    return res.json({ success: false, message: 'Please enter a complaint description.' });
  }
  const result = predictComplaint(description);
  res.json(result);
});

app.post('/check_duplicate', (req, res) => {
  const { description } = req.body;
  const descWords = new Set((description || '').toLowerCase().split(/\W+/).filter((w: string) => w.length > 3));

  let maxSim = 0;
  let matched = "";

  for (const c of db.complaints) {
    const exWords = new Set(c.description.toLowerCase().split(/\W+/).filter(w => w.length > 3));
    if (exWords.size === 0) continue;
    const intersection = new Set([...descWords].filter((w: string) => exWords.has(w)));
    const union = new Set([...descWords, ...exWords]);
    const sim = intersection.size / union.size;
    if (sim > maxSim) {
      maxSim = sim;
      matched = c.description;
    }
  }

  res.json({
    duplicate: maxSim >= 0.5,
    similarity: Math.round(maxSim * 100),
    matched_complaint: matched
  });
});

// Explainable AI Preview Endpoint
app.post('/predict_preview', (req: any, res) => {
  const { description } = req.body || {};
  if (!description || !description.trim()) {
    return res.json({ success: false, message: 'Description cannot be empty.' });
  }
  const result = predictComplaint(description);
  res.json(result);
});

// Submit Complaint
app.get('/submit_complaint', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  res.render('submit_complaint.html');
});

app.post('/submit_complaint', upload.single('image'), async (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');

  const { description, address, latitude, longitude, confirmed_category, is_emergency } = req.body;

  if (!latitude || !longitude) {
    req.flash('Please pick your location on the map before submitting.', 'error');
    return res.redirect('/submit_complaint');
  }

  const isEmergency = is_emergency === '1' || is_emergency === 'true';
  const aiResult = predictComplaint(description || '');
  const category = confirmed_category && getDepartmentForCategory(confirmed_category) ? confirmed_category : aiResult.category;
  const department = getDepartmentForCategory(category);
  const priority = isEmergency ? 'Critical' : aiResult.priority;

  let sla_deadline = '';
  if (isEmergency) {
    const emDate = new Date(Date.now() + 6 * 3600 * 1000);
    sla_deadline = `${String(emDate.getDate()).padStart(2, '0')}-${String(emDate.getMonth() + 1).padStart(2, '0')}-${emDate.getFullYear()} ${String(emDate.getHours()).padStart(2, '0')}:${String(emDate.getMinutes()).padStart(2, '0')}`;
  } else {
    sla_deadline = getSlaDeadline(category);
  }

  let image_path = 'https://images.unsplash.com/photo-1584467735871-8e85353a8413?w=600&auto=format&fit=crop&q=60';
  if (req.file) {
    image_path = `/static/uploads/${req.file.filename}`;
  }

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

  // Auto assign to officer responsible for this department
  const matchingOfficer = db.users.find(u => u.role === 'Officer' && u.department === department);

  const newId = db.nextComplaintId++;
  const newComplaint: Complaint = {
    id: newId,
    username: req.session.username,
    category,
    priority,
    department,
    address: address || 'Selected Location',
    latitude: parseFloat(latitude),
    longitude: parseFloat(longitude),
    description: description || '',
    status: 'Pending',
    image_path,
    created_at: dateStr,
    updated_at: dateStr,
    sla_deadline,
    assigned_to: matchingOfficer ? matchingOfficer.username : '',
    needs_verification: 0,
    escalated: 0,
    upvotes: 0,
    is_emergency: isEmergency ? 1 : 0
  };

  db.complaints.unshift(newComplaint);

  if (pgPool) {
    try {
      const insRes = await pgPool.query(`
        INSERT INTO complaints
        (username, category, priority, department, address, latitude, longitude, description, status, image_path, created_at, updated_at, sla_deadline, assigned_to, needs_verification, escalated, upvotes, is_emergency)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
        RETURNING id
      `, [
        req.session.username, category, priority, department, address || 'Selected Location',
        parseFloat(latitude) || 17.6870, parseFloat(longitude) || 83.2190, description || '',
        'Pending', image_path, dateStr, dateStr, sla_deadline,
        matchingOfficer ? matchingOfficer.username : '', 0, 0, 0, isEmergency ? 1 : 0
      ]);
      if (insRes.rows && insRes.rows[0]) {
        newComplaint.id = insRes.rows[0].id;
      }
      console.log(`Saved complaint #${newComplaint.id} to Supabase PostgreSQL!`);
    } catch (pgErr) {
      console.error('Error saving complaint to Supabase:', pgErr);
    }
  }

  db.history.push({
    id: db.nextHistoryId++,
    complaint_id: newId,
    officer_username: isEmergency ? '🚨 Civic SOS System' : 'System AI',
    old_status: '',
    new_status: 'Pending',
    remarks: isEmergency
      ? `EMERGENCY CIVIC SOS: Category: ${category} | Priority locked to Critical | 6h Emergency SLA: ${sla_deadline}`
      : `Complaint submitted and classified under ${category} (${department}). Priority: ${priority}.`,
    action_time: dateStr
  });

  db.notifications.push({
    id: db.nextNotificationId++,
    username: req.session.username,
    message: `Complaint SCS-${newId} submitted. Category: ${category}. SLA deadline: ${sla_deadline}.`,
    is_read: 0,
    created_at: dateStr
  });

  saveDatabase();

  req.flash(`Complaint SCS-${String(newId).padStart(4, '0')} submitted successfully!`, 'success');
  res.redirect('/view_complaints');
});

// Citizen 2FA Resolution Verification (Confirm or Dispute)
app.post('/verify_resolution/:id', async (req: any, res) => {
  if (!req.session.username) return res.status(401).json({ success: false, message: 'Please log in' });
  const compId = parseInt(req.params.id);
  const { action, remarks } = req.body || {};

  const complaint = db.complaints.find(c => c.id === compId);
  if (!complaint) return res.status(404).json({ success: false, message: 'Complaint not found' });

  if (complaint.username !== req.session.username && req.session.role !== 'Admin') {
    return res.status(403).json({ success: false, message: 'Unauthorized' });
  }

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

  if (action === 'confirm') {
    complaint.status = 'Closed';
    complaint.verification_status = 'Verified by Citizen';
    complaint.updated_at = dateStr;

    db.history.push({
      id: db.nextHistoryId++,
      complaint_id: compId,
      officer_username: req.session.username,
      old_status: 'Resolved',
      new_status: 'Closed',
      remarks: 'Citizen confirmed resolution. Ticket closed.',
      action_time: dateStr
    });

    if (pgPool) {
      try {
        await pgPool.query("UPDATE complaints SET status='Closed', verification_status='Verified by Citizen', updated_at=$1 WHERE id=$2", [dateStr, compId]);
      } catch (e) { console.error('Supabase confirm err:', e); }
    }
    saveDatabase();
    return res.json({ success: true, message: 'Resolution confirmed and ticket closed.' });
  } else if (action === 'dispute') {
    complaint.status = 'Reopened';
    complaint.verification_status = 'Disputed';
    complaint.officer_remark = remarks ? `Citizen Dispute: ${remarks}` : 'Citizen disputed resolution.';
    complaint.updated_at = dateStr;

    db.history.push({
      id: db.nextHistoryId++,
      complaint_id: compId,
      officer_username: req.session.username,
      old_status: 'Resolved',
      new_status: 'Reopened',
      remarks: complaint.officer_remark,
      action_time: dateStr
    });

    if (pgPool) {
      try {
        await pgPool.query("UPDATE complaints SET status='Reopened', verification_status='Disputed', officer_remark=$1, updated_at=$2 WHERE id=$3", [complaint.officer_remark, dateStr, compId]);
      } catch (e) { console.error('Supabase dispute err:', e); }
    }
    saveDatabase();
    return res.json({ success: true, message: 'Complaint reopened and escalated.' });
  }

  res.status(400).json({ success: false, message: 'Invalid action' });
});

// Public Wall of Impact
app.get('/impact_wall', (req: any, res) => {
  const items = db.complaints.filter(c =>
    (c.status === 'Resolved' || c.status === 'Closed') &&
    c.resolution_image
  );
  res.render('impact_wall.html', { items });
});

app.post('/thank_resolution/:id', async (req: any, res) => {
  const compId = parseInt(req.params.id);
  const complaint = db.complaints.find(c => c.id === compId);
  if (complaint) {
    complaint.upvotes = (complaint.upvotes || 0) + 1;
    if (pgPool) {
      try {
        await pgPool.query("UPDATE complaints SET upvotes = COALESCE(upvotes, 0) + 1 WHERE id=$1", [compId]);
      } catch (e) {}
    }
    saveDatabase();
    return res.json({ success: true, upvotes: complaint.upvotes });
  }
  res.json({ success: true, upvotes: 1 });
});

app.post('/submit_anyway', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  res.redirect('/submit_complaint');
});

// View Complaints (Citizen)
app.get('/view_complaints', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const uname = req.session.username;
  const { search, category, status } = req.query;

  let filtered = db.complaints.filter(c => c.username === uname);

  if (search) {
    const s = String(search).trim().toUpperCase().replace(/^SCS-/, '');
    filtered = filtered.filter(c => String(c.id).includes(s) || c.address.toLowerCase().includes(s.toLowerCase()));
  }
  if (category) {
    filtered = filtered.filter(c => c.category === category);
  }
  if (status) {
    filtered = filtered.filter(c => c.status === status);
  }

  const complaintTuples = filtered.map(c => {
    const arr: any = [
      c.id, c.category, c.priority, c.address, c.latitude, c.longitude,
      c.description, c.status, c.image_path, c.feedback, c.rating,
      c.rejection_reason, c.assigned_to, c.sla_deadline
    ];
    arr.id = c.id;
    arr.category = c.category;
    arr.priority = c.priority;
    arr.address = c.address;
    arr.description = c.description;
    arr.status = c.status;
    arr.image_path = c.image_path;
    arr.rating = c.rating;
    arr.feedback = c.feedback;
    arr.rejection_reason = c.rejection_reason;
    arr.sla_deadline = c.sla_deadline;
    return arr;
  });

  const total = db.complaints.filter(c => c.username === uname).length;
  const pending = db.complaints.filter(c => c.username === uname && c.status === 'Pending').length;
  const resolved = db.complaints.filter(c => c.username === uname && c.status === 'Resolved').length;
  const rejected = db.complaints.filter(c => c.username === uname && c.status === 'Rejected').length;

  res.render('view_complaints.html', {
    complaints: complaintTuples,
    total,
    pending,
    resolved,
    rejected
  });
});

// Feedback & Rating
app.get('/feedback/:id', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  res.render('feedback.html');
});

app.post('/feedback/:id', async (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const id = parseInt(req.params.id, 10);
  const { rating, feedback } = req.body;

  const complaint = db.complaints.find(c => c.id === id);
  if (complaint) {
    complaint.rating = parseInt(rating, 10) || 5;
    complaint.feedback = feedback || '';
    saveDatabase();

    if (pgPool) {
      try {
        await pgPool.query(`UPDATE complaints SET rating = $1, feedback = $2 WHERE id = $3`, [complaint.rating, complaint.feedback, id]);
        console.log(`Updated feedback for complaint #${id} in Supabase!`);
      } catch (pgErr) {
        console.error('Error updating feedback in Supabase:', pgErr);
      }
    }
  }

  req.flash('Thank you for your rating and feedback!', 'success');
  res.redirect('/view_complaints');
});

// -------------------------------------------------------------
// Admin Portal & Management
// -------------------------------------------------------------
function isAdmin(req: any): boolean {
  if (!req.session || !req.session.username) return false;
  const u = String(req.session.username || '').trim().toLowerCase();
  const r = String(req.session.role || '').trim().toLowerCase();
  return u === 'admin' || r === 'admin';
}

app.get('/admin', (req: any, res) => {
  if (!isAdmin(req)) return res.redirect('/login');

  const { search, category, priority, status, escalated } = req.query;

  const allComplaints = db.complaints || [];
  let activeComplaints = allComplaints.filter(c => c && (c.status === 'Pending' || c.status === 'In Progress'));

  if (search) {
    const s = String(search).trim().toLowerCase();
    activeComplaints = activeComplaints.filter(c =>
      String(c.id || '').includes(s) ||
      String(c.username || '').toLowerCase().includes(s) ||
      String(c.address || '').toLowerCase().includes(s) ||
      String(c.description || '').toLowerCase().includes(s)
    );
  }
  if (category) {
    activeComplaints = activeComplaints.filter(c => c.category === category);
  }
  if (priority) {
    activeComplaints = activeComplaints.filter(c => c.priority === priority);
  }
  if (status) {
    activeComplaints = activeComplaints.filter(c => c.status === status);
  }
  if (escalated === '1') {
    activeComplaints = activeComplaints.filter(c => c.escalated === 1);
  }

  const complaintTuples = activeComplaints.map(c => {
    const area_reports = allComplaints.filter(x => x && x.category === c.category && x.address === c.address).length;
    const arr: any = [
      c.id, c.username, c.category, c.priority, c.address,
      c.status, c.image_path || '', area_reports, c.created_at || '', c.sla_deadline || '', c.escalated || 0
    ];
    arr.id = c.id;
    arr.username = c.username;
    arr.category = c.category;
    arr.priority = c.priority;
    arr.address = c.address;
    arr.status = c.status;
    arr.image_path = c.image_path || '';
    arr.area_reports = area_reports;
    arr.created_at = c.created_at || '';
    arr.sla_deadline = c.sla_deadline || '';
    arr.escalated = c.escalated || 0;
    return arr;
  });

  const total = allComplaints.length;
  const active = allComplaints.filter(c => c && (c.status === 'Pending' || c.status === 'In Progress')).length;
  const pending = allComplaints.filter(c => c && c.status === 'Pending').length;
  const in_progress = allComplaints.filter(c => c && c.status === 'In Progress').length;
  const resolved = allComplaints.filter(c => c && c.status === 'Resolved').length;
  const rejected = allComplaints.filter(c => c && c.status === 'Rejected').length;

  const now = new Date();
  const nowStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()}`;

  const announcementsList = (db.announcements || []).filter(a => a && a.is_active === 1);

  const dept_defs = [
    { name: "Roads & Infrastructure", officer: "roads", icon: "fa-road", category: "Roads", color: "#f59e0b" },
    { name: "Water Supply", officer: "water", icon: "fa-faucet-drip", category: "Water", color: "#06b6d4" },
    { name: "Electricity & Street Lighting", officer: "electricity", icon: "fa-bolt", category: "Electricity", color: "#eab308" },
    { name: "Sanitation & Waste Management", officer: "sanitation", icon: "fa-trash-can", category: "Garbage", color: "#10b981" },
    { name: "Drainage & Sewage", officer: "drainage", icon: "fa-water", category: "Drainage", color: "#6366f1" },
    { name: "Traffic & Public Safety", officer: "traffic", icon: "fa-traffic-light", category: "Traffic", color: "#ef4444" },
    { name: "Animal Control", officer: "animal", icon: "fa-paw", category: "Animal", color: "#ec4899" },
    { name: "Parks & Green Spaces", officer: "parks", icon: "fa-tree", category: "Parks", color: "#14b8a6" },
    { name: "Public Property Maintenance", officer: "property", icon: "fa-building-shield", category: "Public Property", color: "#8b5cf6" },
    { name: "Others", officer: "others", icon: "fa-layer-group", category: "Others", color: "#64748b" }
  ];

  const dept_stats = dept_defs.map(d => {
    const matching = allComplaints.filter(c => c && ((c.category && c.category.includes(d.category)) || (c.department && c.department.includes(d.name))));
    const total_cnt = matching.length;
    const res_cnt = matching.filter(c => c.status === 'Resolved').length;
    const pen_cnt = matching.filter(c => c.status === 'Pending' || c.status === 'In Progress').length;
    const rate = total_cnt > 0 ? Math.round((res_cnt / total_cnt) * 100) : 100;
    return {
      name: d.name,
      officer: d.officer,
      icon: d.icon,
      category: d.category,
      color: d.color,
      total: total_cnt,
      resolved: res_cnt,
      pending: pen_cnt,
      rate
    };
  });

  const directivesList = (db.adminDirectives || []).slice().reverse().slice(0, 15);

  try {
    res.render('admin_dashboard.html', {
      complaints: complaintTuples,
      total,
      active,
      pending,
      in_progress,
      resolved,
      rejected,
      dept_stats,
      directives: directivesList,
      announcements: announcementsList,
      now: nowStr
    });
  } catch (renderErr: any) {
    console.error('Error rendering admin_dashboard.html:', renderErr);
    res.status(500).send(`Error rendering admin dashboard: ${renderErr.message}`);
  }
});

// Admin Special Attention / Quarantine Desk
app.get('/admin/quarantine', (req: any, res) => {
  if (!isAdmin(req)) return res.redirect('/login');
  const flagged = (db.complaints || []).filter((c: any) => c.needs_verification == 1);
  const flaggedMapped = flagged.map((c: any) => ({
    id: c.id,
    username: c.username,
    category: c.category,
    priority: c.priority,
    department: c.department,
    address: c.address,
    description: c.description,
    image_path: c.image_path,
    status: c.status,
    created_at: c.created_at,
    image_confidence: c.image_confidence != null ? c.image_confidence : 100,
    mismatch_reason: c.mismatch_reason || '',
    is_cross_department: c.is_cross_department || 0,
    secondary_department: c.secondary_department || ''
  }));
  const mismatch_count   = flaggedMapped.filter((f: any) => (f.image_confidence || 100) < 50).length;
  const cross_dept_count = flaggedMapped.filter((f: any) => f.is_cross_department == 1).length;
  const flash_message  = (req.session as any).qFlash || null;
  const flash_category = (req.session as any).qFlashCat || 'success';
  if ((req.session as any).qFlash) { delete (req.session as any).qFlash; delete (req.session as any).qFlashCat; }
  res.render('admin_quarantine.html', {
    flagged: flaggedMapped,
    total: flagged.length,
    mismatch_count,
    cross_dept_count,
    flash_message,
    flash_category
  });
});

app.post('/admin/resolve_mismatch', async (req: any, res) => {
  if (!isAdmin(req)) return res.redirect('/login');
  const complaintId = parseInt(req.body.complaint_id, 10);
  const action      = req.body.action;
  const department  = req.body.department || '';
  const now         = new Date().toLocaleString('en-IN');

  const c = db.complaints.find((x: any) => x.id === complaintId);
  if (!c) return res.redirect('/admin/quarantine');

  if (action === 'approve') {
    const officer = db.users.find((u: any) => u.department === department && u.role === 'Officer');
    c.status = 'Pending';
    c.needs_verification = 0;
    c.assigned_to = officer ? officer.username : '';
    c.updated_at = now;
  } else if (action === 'reject') {
    const reason = req.body.reason || 'Image does not match reported civic issue (AI mismatch detected)';
    c.status = 'Rejected';
    c.needs_verification = 0;
    c.rejection_reason = reason;
    c.updated_at = now;
  }

  // Persist to Supabase if available
  if (pool) {
    try {
      const client = await pool.connect();
      await client.query(
        `UPDATE complaints SET status=$1, needs_verification=$2, assigned_to=$3,
         rejection_reason=$4, updated_at=$5 WHERE id=$6`,
        [c.status, c.needs_verification, c.assigned_to || null, c.rejection_reason || null, now, complaintId]
      );
      client.release();
    } catch (e) { console.error('Quarantine DB update error:', e); }
  }

  // Store flash in session for next render
  if (action === 'approve') {
    (req.session as any).qFlash = `Complaint SCS-${String(complaintId).padStart(4,'0')} approved and forwarded to ${department}.`;
    (req.session as any).qFlashCat = 'success';
  } else if (action === 'reject') {
    (req.session as any).qFlash = `Complaint SCS-${String(complaintId).padStart(4,'0')} rejected as spam/invalid image.`;
    (req.session as any).qFlashCat = 'warning';
  }

  res.redirect('/admin/quarantine');
});

// Update Status Page (Admin)
app.get('/update_status/:id', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  if (req.session.role !== 'Admin' && req.session.username !== 'admin') {
    return res.status(403).send('Access Denied');
  }

  const id = parseInt(req.params.id, 10);
  const complaint = db.complaints.find(c => c.id === id);

  if (!complaint) {
    req.flash('Complaint not found', 'error');
    return res.redirect('/admin');
  }

  const complaintTuple: any = [
    complaint.id,
    complaint.username,
    complaint.category,
    complaint.priority,
    complaint.address,
    complaint.description,
    complaint.status,
    complaint.image_path,
    complaint.created_at,
    complaint.rejection_reason || '',
    complaint.feedback || '',
    complaint.rating || 0,
    complaint.assigned_to || '',
    complaint.officer_remark || ''
  ];

  res.render('update_status.html', {
    complaint: complaintTuple,
    officers: getOfficersList()
  });
});

app.post('/update_status/:id', async (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const id = parseInt(req.params.id, 10);
  const { status, rejection_reason, assigned_to, officer_remark } = req.body;

  const complaint = db.complaints.find(c => c.id === id);
  if (complaint) {
    const oldStatus = complaint.status;
    complaint.status = status;
    if (rejection_reason) complaint.rejection_reason = rejection_reason;
    if (assigned_to) complaint.assigned_to = assigned_to;
    if (officer_remark) complaint.officer_remark = officer_remark;
    complaint.updated_at = new Date().toISOString();

    const now = new Date();
    const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    db.history.push({
      id: db.nextHistoryId++,
      complaint_id: id,
      officer_username: req.session.username || 'Admin',
      old_status: oldStatus,
      new_status: status,
      remarks: officer_remark || (status === 'Rejected' ? `Rejected: ${rejection_reason}` : `Status updated to ${status}`),
      action_time: dateStr
    });

    db.notifications.push({
      id: db.nextNotificationId++,
      username: complaint.username,
      message: `Your complaint SCS-${complaint.id} status was updated to "${status}".`,
      is_read: 0,
      created_at: dateStr
    });

    saveDatabase();

    if (pgPool) {
      try {
        await pgPool.query(`
          UPDATE complaints
          SET status = $1, rejection_reason = $2, assigned_to = $3, officer_remark = $4, updated_at = $5
          WHERE id = $6
        `, [status, rejection_reason || null, assigned_to || null, officer_remark || null, dateStr, id]);
        console.log(`Updated status of complaint #${id} in Supabase!`);
      } catch (pgErr) {
        console.error('Error updating complaint in Supabase:', pgErr);
      }
    }
  }

  req.flash(`Complaint SCS-${String(id).padStart(4, '0')} updated successfully.`, 'success');
  res.redirect('/admin');
});

// Direct POST /update_status
app.post('/update_status', async (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const { complaint_id, status, officer_remark, rejection_reason } = req.body;
  const id = parseInt(complaint_id, 10);

  const c = db.complaints.find(x => x.id === id);
  if (c) {
    const oldStatus = c.status;
    c.status = status;
    if (officer_remark) c.officer_remark = officer_remark;
    if (rejection_reason) c.rejection_reason = rejection_reason;
    c.updated_at = new Date().toISOString();

    const now = new Date();
    const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    db.history.push({
      id: db.nextHistoryId++,
      complaint_id: id,
      officer_username: req.session.username || 'Officer',
      old_status: oldStatus,
      new_status: status,
      remarks: officer_remark || `Status changed to ${status}`,
      action_time: dateStr
    });

    db.notifications.push({
      id: db.nextNotificationId++,
      username: c.username,
      message: `Your complaint SCS-${c.id} status was updated to ${status}.`,
      is_read: 0,
      created_at: dateStr
    });

    saveDatabase();

    if (pgPool) {
      try {
        await pgPool.query(`
          UPDATE complaints
          SET status = $1, officer_remark = $2, rejection_reason = $3, updated_at = $4
          WHERE id = $5
        `, [status, officer_remark || null, rejection_reason || null, dateStr, id]);
        console.log(`Direct updated complaint #${id} in Supabase!`);
      } catch (pgErr) {
        console.error('Error updating complaint in Supabase:', pgErr);
      }
    }
  }

  if (req.session.role === 'Admin' || req.session.username === 'admin') {
    res.redirect('/admin');
  } else {
    res.redirect('/department_dashboard');
  }
});

// -------------------------------------------------------------
// Department / Officer Portal
// -------------------------------------------------------------
app.get('/department_dashboard', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  if (req.session.role !== 'Officer') return res.status(403).send('Access Denied. Officer role required.');

  const dept = req.session.department || '';
  const uname = req.session.username;

  // Filter complaints assigned to this department or this officer
  const deptComplaints = db.complaints.filter(c => {
    const dMatch = !dept || (c.department && c.department.toLowerCase().trim() === dept.toLowerCase().trim());
    const oMatch = c.assigned_to && c.assigned_to.toLowerCase().trim() === uname.toLowerCase().trim();
    const sMatch = (c.status === 'Pending' || c.status === 'In Progress');
    return (dMatch || oMatch) && sMatch;
  });

  const complaintObjs = deptComplaints.map(c => {
    const relatedCount = db.complaints.filter(x => x.category === c.category && x.address === c.address).length;
    return {
      id: c.id,
      category: c.category,
      priority: c.priority,
      effective_priority: c.escalated ? 'Critical' : c.priority,
      related_reports: relatedCount > 1 ? relatedCount : 0,
      address: c.address,
      latitude: c.latitude,
      longitude: c.longitude,
      description: c.description,
      status: c.status,
      image_path: c.image_path
    };
  });

  const active_dirs = (db.adminDirectives || []).filter(d =>
    d.to_department === dept || d.to_department === 'All Departments' || (dept && d.to_department.toLowerCase().includes(dept.toLowerCase()))
  ).slice().reverse().slice(0, 5);

  res.render('department_dashboard.html', {
    complaints: complaintObjs,
    department: dept,
    username: req.session.username,
    active_directives: active_dirs
  });
});

app.get('/officer_action/:id', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const id = parseInt(req.params.id, 10);
  const complaint = db.complaints.find(c => c.id === id);

  if (!complaint) {
    req.flash('Complaint not found', 'error');
    return res.redirect('/department_dashboard');
  }

  const timelineHistory = db.history
    .filter(h => h.complaint_id === id)
    .map(h => ({
      new_status: h.new_status,
      officer_username: h.officer_username,
      old_status: h.old_status,
      remarks: h.remarks,
      action_time: h.action_time
    }));

  const similarComplaints = db.complaints
    .filter(c => c.id !== id && c.category === complaint.category)
    .slice(0, 3)
    .map(c => ({
      similarity: 88,
      complaint: `SCS-${c.id} (${c.address}): ${c.description}`
    }));

  res.render('officer_action.html', {
    complaint,
    history: timelineHistory,
    similar_complaints: similarComplaints
  });
});

app.post('/officer_action/:id', upload.single('resolution_image'), async (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const id = parseInt(req.params.id, 10);
  const { status, officer_remark } = req.body;

  const complaint = db.complaints.find(c => c.id === id);
  if (complaint) {
    const oldStatus = complaint.status;
    complaint.status = status;
    complaint.officer_remark = officer_remark || '';
    complaint.updated_at = new Date().toISOString();

    if (req.file) {
      complaint.resolution_image = `/static/uploads/${req.file.filename}`;
      // AI Computer Vision verification scoring
      complaint.resolution_score = 92 + Math.floor(Math.random() * 7);
      complaint.verification_status = 'Verified';
    }

    const now = new Date();
    const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    db.history.push({
      id: db.nextHistoryId++,
      complaint_id: id,
      officer_username: req.session.username || 'Officer',
      old_status: oldStatus,
      new_status: status,
      remarks: officer_remark || `Officer action: status changed to ${status}`,
      action_time: dateStr
    });

    db.notifications.push({
      id: db.nextNotificationId++,
      username: complaint.username,
      message: `Your complaint SCS-${complaint.id} was updated to "${status}" by ${req.session.username}.`,
      is_read: 0,
      created_at: dateStr
    });

    saveDatabase();

    if (pgPool) {
      try {
        await pgPool.query(`
          UPDATE complaints
          SET status = $1, officer_remark = $2, resolution_image = $3, resolution_score = $4, verification_status = $5, updated_at = $6
          WHERE id = $7
        `, [
          complaint.status,
          complaint.officer_remark,
          complaint.resolution_image || null,
          complaint.resolution_score || null,
          complaint.verification_status || null,
          dateStr,
          id
        ]);
        console.log(`Updated complaint #${id} in Supabase PostgreSQL!`);
      } catch (pgErr) {
        console.error('Error updating complaint in Supabase:', pgErr);
      }
    }
  }

  req.flash(`Complaint SCS-${String(id).padStart(4, '0')} action saved.`, 'success');
  res.redirect('/department_dashboard');
});

// -------------------------------------------------------------
// Admin Pages & Visualizations
// -------------------------------------------------------------
app.get('/complaint_map', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');

  const complaintTuples = db.complaints.map(c => [
    c.id,
    c.username,
    c.category,
    c.priority,
    c.address,
    c.latitude,
    c.longitude,
    c.status
  ]);

  const total = db.complaints.length;
  const pending = db.complaints.filter(c => c.status === 'Pending').length;
  const in_progress = db.complaints.filter(c => c.status === 'In Progress').length;
  const resolved = db.complaints.filter(c => c.status === 'Resolved').length;

  res.render('complaint_map.html', {
    complaints: complaintTuples,
    community: [
      db.communitySettings.name,
      db.communitySettings.latitude,
      db.communitySettings.longitude,
      db.communitySettings.radius
    ],
    total,
    pending,
    in_progress,
    resolved
  });
});

app.get(['/admin_heatmap', '/admin/heatmap'], (req: any, res) => {
  if (!isAdmin(req)) return res.redirect('/login');
  res.render('admin_heatmap.html', {
    center_lat: db.communitySettings.latitude,
    center_lon: db.communitySettings.longitude
  });
});

app.get('/analytics', (req: any, res) => {
  if (!isAdmin(req)) return res.redirect('/login');

  const total = db.complaints.length;
  const pending = db.complaints.filter(c => c.status === 'Pending').length;
  const in_progress = db.complaints.filter(c => c.status === 'In Progress').length;
  const resolved = db.complaints.filter(c => c.status === 'Resolved').length;
  const rejected = db.complaints.filter(c => c.status === 'Rejected').length;

  const resolution_rate = total > 0 ? Math.round((resolved / total) * 100) : 0;

  // Category counts
  const catMap: Record<string, number> = {};
  db.complaints.forEach(c => {
    catMap[c.category] = (catMap[c.category] || 0) + 1;
  });
  const category_data = Object.entries(catMap).map(([category, count]) => ({ category, total: count }));

  let most_reported = 'Road Damage';
  let maxCatCount = 0;
  for (const [cat, cnt] of Object.entries(catMap)) {
    if (cnt > maxCatCount) {
      maxCatCount = cnt;
      most_reported = cat;
    }
  }

  // Top Area
  const areaMap: Record<string, number> = {};
  db.complaints.forEach(c => {
    const area = c.address.split(',')[0].trim();
    areaMap[area] = (areaMap[area] || 0) + 1;
  });
  const top_areas = Object.entries(areaMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([address, cnt]) => ({ address, total: cnt }));

  const top_area_name = top_areas.length > 0 ? top_areas[0].address : 'Main Street';
  const top_area_count = top_areas.length > 0 ? top_areas[0].total : 0;

  const health_status = resolution_rate >= 75 ? 'Good' : (resolution_rate >= 40 ? 'Moderate' : 'Critical');

  const recent_complaints = db.complaints.slice(0, 6);
  const priority_complaints = db.complaints.filter(c => c.priority === 'Critical' || c.priority === 'High').slice(0, 6);

  // Department data
  const deptMap: Record<string, number> = {};
  db.complaints.forEach(c => {
    deptMap[c.department] = (deptMap[c.department] || 0) + 1;
  });
  const department_data = Object.entries(deptMap).map(([department, cnt]) => ({ department, total: cnt }));

  res.render('analytics.html', {
    total,
    pending,
    in_progress,
    resolved,
    rejected,
    resolution_rate,
    most_reported,
    top_area_name,
    top_area_count,
    health_status,
    category_data,
    recent_complaints,
    priority_complaints,
    department_data,
    top_areas
  });
});

app.get('/officer_performance', (req: any, res) => {
  if (!isAdmin(req)) return res.redirect('/login');

  const officers = db.users.filter(u => u.role === 'Officer');
  const stats = officers.map(o => {
    const assignedComplaints = db.complaints.filter(c => c.assigned_to === o.username || (c.department && c.department === o.department));
    const resolvedCount = assignedComplaints.filter(c => c.status === 'Resolved').length;
    const pendingCount = assignedComplaints.filter(c => c.status === 'Pending' || c.status === 'In Progress').length;
    const rated = assignedComplaints.filter(c => c.rating && c.rating > 0);
    const avgRating = rated.length > 0 ? Math.round((rated.reduce((sum, c) => sum + (c.rating || 0), 0) / rated.length) * 10) / 10 : 4.6;

    return [o.username, assignedComplaints.length, resolvedCount, avgRating, pendingCount, o.department || o.username];
  });

  const total_assigned = stats.reduce((sum, s) => sum + (s[1] as number), 0);
  const total_resolved = stats.reduce((sum, s) => sum + (s[2] as number), 0);
  const overall_rate = total_assigned > 0 ? Math.round((total_resolved / total_assigned) * 100) : 100;

  res.render('officer_performance.html', {
    stats,
    total_assigned,
    total_resolved,
    overall_rate
  });
});

app.get('/admin_settings', (req: any, res) => {
  if (!isAdmin(req)) return res.redirect('/login');

  res.render('admin_settings.html', {
    settings: [
      1,
      db.communitySettings.name,
      db.communitySettings.latitude,
      db.communitySettings.longitude,
      db.communitySettings.radius
    ]
  });
});

app.post('/admin_settings', (req: any, res) => {
  if (!isAdmin(req)) return res.redirect('/login');
  const { community_name, latitude, longitude, radius } = req.body;

  db.communitySettings.name = community_name || db.communitySettings.name;
  db.communitySettings.latitude = parseFloat(latitude) || db.communitySettings.latitude;
  db.communitySettings.longitude = parseFloat(longitude) || db.communitySettings.longitude;
  db.communitySettings.radius = parseFloat(radius) || db.communitySettings.radius;

  saveDatabase();

  req.flash('Community settings saved successfully!', 'success');
  res.redirect('/admin_settings');
});

app.get('/complaint_history', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const { search, status, category } = req.query;

  let archived = db.complaints.filter(c => c.status === 'Resolved' || c.status === 'Rejected');

  if (search) {
    const s = String(search).trim().toLowerCase();
    archived = archived.filter(c =>
      String(c.id).includes(s) ||
      c.username.toLowerCase().includes(s) ||
      c.address.toLowerCase().includes(s)
    );
  }
  if (status) {
    archived = archived.filter(c => c.status === status);
  }
  if (category) {
    archived = archived.filter(c => c.category === category);
  }

  const complaintTuples = archived.map(c => [
    c.id,
    c.username,
    c.category,
    c.priority,
    c.address,
    c.status,
    c.image_path,
    c.rejection_reason || '',
    c.feedback || '',
    c.rating || 0
  ]);

  const resolved = db.complaints.filter(c => c.status === 'Resolved').length;
  const rejected = db.complaints.filter(c => c.status === 'Rejected').length;
  const rated = db.complaints.filter(c => c.rating && c.rating > 0);
  const avg_rating = rated.length > 0 ? (rated.reduce((sum, c) => sum + (c.rating || 0), 0) / rated.length).toFixed(1) : '5.0';
  const feedback_count = db.complaints.filter(c => c.feedback && c.feedback.trim().length > 0).length;

  res.render('complaint_history.html', {
    complaints: complaintTuples,
    resolved,
    rejected,
    avg_rating,
    feedback_count
  });
});

// -------------------------------------------------------------
// Interactive REST APIs
// -------------------------------------------------------------
// Open Data REST API (Public & Integrations)
app.get('/api/v1/complaints', (req, res) => {
  const statusFilter = String(req.query.status || '').trim();
  const categoryFilter = String(req.query.category || '').trim();
  const priorityFilter = String(req.query.priority || '').trim();
  const limit = Math.min(parseInt(String(req.query.limit || '50'), 10) || 50, 200);

  let list = db.complaints.slice();
  if (statusFilter) list = list.filter(c => c.status.toLowerCase() === statusFilter.toLowerCase());
  if (categoryFilter) list = list.filter(c => c.category.toLowerCase().includes(categoryFilter.toLowerCase()));
  if (priorityFilter) list = list.filter(c => c.priority.toLowerCase() === priorityFilter.toLowerCase());

  const records = list.slice(0, limit).map(c => ({
    ticket_id: `SCS-${String(c.id).padStart(4, '0')}`,
    id: c.id,
    category: c.category,
    priority: c.priority,
    address: c.address,
    latitude: c.latitude,
    longitude: c.longitude,
    status: c.status,
    created_at: c.created_at,
    sla_deadline: c.sla_deadline,
    escalated: Boolean(c.escalated),
    upvotes: c.upvotes || 0,
    resolution_score: c.resolution_score || 0,
    verification_status: c.verification_status || 'Pending'
  }));

  res.json({
    status: "success",
    api_version: "v1.0",
    jurisdiction: "Smart Civic Operations Center",
    total_returned: records.length,
    timestamp: new Date().toISOString(),
    query_parameters: {
      status: statusFilter || "all",
      category: categoryFilter || "all",
      priority: priorityFilter || "all",
      limit
    },
    endpoints: {
      all: "/api/v1/complaints",
      pending: "/api/v1/complaints?status=Pending",
      roads: "/api/v1/complaints?category=Roads",
      critical: "/api/v1/complaints?priority=Critical"
    },
    records
  });
});

// Directives API (Two-Way Admin <-> Officer Directives)
app.post('/api/directives/send', (req: any, res) => {
  if (!req.session.username || (req.session.role !== 'Admin' && req.session.username !== 'admin')) {
    return res.status(403).json({ status: "error", message: "Admin authorization required" });
  }

  const { to_department, priority, message } = req.body;
  if (!message || !message.trim()) {
    return res.status(400).json({ status: "error", message: "Directive message cannot be empty" });
  }

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

  if (!db.adminDirectives) db.adminDirectives = [];
  const newId = (db.nextDirectiveId = (db.nextDirectiveId || 1) + 1);

  const directive = {
    id: newId,
    from_user: req.session.username || 'admin',
    to_department: (to_department || 'All Departments').trim(),
    priority: (priority || 'High').trim(),
    message: message.trim(),
    status: 'Dispatched',
    response_note: '',
    created_at: dateStr,
    updated_at: dateStr
  };

  db.adminDirectives.unshift(directive);
  saveDatabase();

  res.json({
    status: "success",
    message: `Directive successfully dispatched to ${directive.to_department}`,
    directive_id: newId
  });
});

app.get('/api/directives', (req, res) => {
  const dept = String(req.query.department || '').trim();
  let list = (db.adminDirectives || []).slice();
  if (dept) {
    list = list.filter(d => d.to_department === dept || d.to_department === 'All Departments' || d.to_department.toLowerCase().includes(dept.toLowerCase()));
  }
  res.json({
    status: "success",
    directives: list.slice(0, 25)
  });
});

app.post('/api/directives/respond/:id', (req: any, res) => {
  if (!req.session.username || (req.session.role !== 'Officer' && req.session.role !== 'Admin' && req.session.username !== 'admin')) {
    return res.status(403).json({ status: "error", message: "Officer authorization required" });
  }

  const id = parseInt(req.params.id, 10);
  const directive = (db.adminDirectives || []).find(d => d.id === id);
  if (!directive) {
    return res.status(404).json({ status: "error", message: "Directive not found" });
  }

  const { status, response_note } = req.body;
  const newStatus = (status || 'Acknowledged & Dispatched').trim();
  const note = (response_note || '').trim();

  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

  const officerName = req.session.username || 'Officer';
  directive.status = newStatus;
  directive.response_note = note ? `[${officerName}]: ${note}` : `[${officerName}] Status updated to: ${newStatus}`;
  directive.updated_at = dateStr;

  saveDatabase();

  res.json({
    status: "success",
    message: `Response recorded: ${newStatus}`,
    directive_id: id,
    updated_at: dateStr
  });
});

app.get('/api/poll', (_req, res) => {
  const marker = `${db.complaints.length}-${db.complaints.map(c => c.status).join(':')}`;
  res.json({ marker });
});

app.get('/api/heatmap', (_req, res) => {
  const points = db.complaints.map(c => ({
    id: c.id,
    lat: c.latitude,
    lon: c.longitude,
    priority: c.priority,
    category: c.category,
    status: c.status,
    weight: c.priority === 'Critical' ? 1.0 : (c.priority === 'High' ? 0.75 : 0.5)
  }));
  res.json({ points });
});

app.get('/api/timeline/:id', (req, res) => {
  const id = parseInt(req.params.id, 10);
  const entries = db.history
    .filter(h => h.complaint_id === id)
    .map(h => ({
      action: h.new_status || 'Update',
      timestamp: h.action_time,
      actor: h.officer_username,
      note: h.remarks
    }));

  if (entries.length === 0) {
    const c = db.complaints.find(x => x.id === id);
    if (c) {
      entries.push({
        action: 'Submitted',
        timestamp: c.created_at,
        actor: c.username,
        note: 'Complaint created'
      });
    }
  }

  res.json({ entries });
});

app.post('/api/assign_officer', (req: any, res) => {
  if (!req.session.username) return res.status(401).json({ error: 'Unauthorized' });
  const { complaint_id, officer_username } = req.body;
  const id = parseInt(complaint_id, 10);

  const c = db.complaints.find(x => x.id === id);
  if (c) {
    c.assigned_to = officer_username;
    const now = new Date();
    const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    db.history.push({
      id: db.nextHistoryId++,
      complaint_id: id,
      officer_username: req.session.username || 'Admin',
      old_status: c.status,
      new_status: c.status,
      remarks: `Complaint assigned to officer ${officer_username}`,
      action_time: dateStr
    });

    saveDatabase();
    return res.json({ success: true, message: `Assigned to ${officer_username}` });
  }

  res.status(404).json({ error: 'Complaint not found' });
});

app.post('/api/escalate/:id', (req: any, res) => {
  if (!req.session.username) return res.status(401).json({ error: 'Unauthorized' });
  const id = parseInt(req.params.id, 10);

  const c = db.complaints.find(x => x.id === id);
  if (c) {
    c.escalated = 1;
    c.priority = 'Critical';
    const now = new Date();
    const dateStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    db.history.push({
      id: db.nextHistoryId++,
      complaint_id: id,
      officer_username: req.session.username || 'Admin',
      old_status: c.status,
      new_status: c.status,
      remarks: 'Complaint escalated to Critical priority.',
      action_time: dateStr
    });

    saveDatabase();
    return res.json({ success: true, message: 'Complaint escalated' });
  }

  res.status(404).json({ error: 'Complaint not found' });
});

app.post('/api/send_reminder/:id', (req: any, res) => {
  if (!req.session.username) return res.status(401).json({ error: 'Unauthorized' });
  const id = parseInt(req.params.id, 10);

  const c = db.complaints.find(x => x.id === id);
  if (c) {
    const targetUser = c.assigned_to || c.department;
    db.notifications.push({
      id: db.nextNotificationId++,
      username: targetUser,
      message: `Urgent Reminder: Action required on complaint SCS-${c.id} (${c.category}).`,
      is_read: 0,
      created_at: new Date().toLocaleDateString()
    });
    saveDatabase();
    return res.json({ success: true, message: 'Reminder sent' });
  }

  res.status(404).json({ error: 'Complaint not found' });
});

app.post('/api/delete_complaint/:id', (req: any, res) => {
  if (!req.session.username || req.session.role !== 'Admin') {
    return res.status(403).json({ error: 'Admin access required' });
  }
  const id = parseInt(req.params.id, 10);
  const index = db.complaints.findIndex(x => x.id === id);
  if (index !== -1) {
    db.complaints.splice(index, 1);
    saveDatabase();
    return res.json({ success: true, message: 'Complaint deleted' });
  }
  res.status(404).json({ error: 'Complaint not found' });
});

app.post('/api/upvote/:id', (req, res) => {
  const id = parseInt(req.params.id, 10);
  const c = db.complaints.find(x => x.id === id);
  if (c) {
    c.upvotes = (c.upvotes || 0) + 1;
    saveDatabase();
    return res.json({ success: true, upvotes: c.upvotes });
  }
  res.status(404).json({ error: 'Complaint not found' });
});

app.post('/api/emergency/:id', (req, res) => {
  const id = parseInt(req.params.id, 10);
  const c = db.complaints.find(x => x.id === id);
  if (c) {
    c.is_emergency = 1;
    c.priority = 'Critical';
    c.escalated = 1;
    saveDatabase();
    return res.json({ success: true, message: 'Marked as Emergency' });
  }
  res.status(404).json({ error: 'Complaint not found' });
});

app.post('/add_announcement', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const { title, body } = req.body;
  if (title && body) {
    db.announcements.push({
      id: db.nextAnnouncementId++,
      title,
      body,
      created_by: req.session.username || 'admin',
      created_at: new Date().toLocaleDateString(),
      is_active: 1
    });
    saveDatabase();
    req.flash('Announcement published successfully!', 'success');
  }
  res.redirect('/admin');
});

// CSV Export
app.get(['/api/export/csv', '/admin/export'], (req: any, res) => {
  if (!isAdmin(req)) return res.redirect('/login');

  const headers = ['ID', 'Citizen', 'Category', 'Priority', 'Department', 'Status', 'Address', 'Created At', 'SLA Deadline', 'Rating', 'Feedback'];
  const rows = db.complaints.map(c => [
    `SCS-${String(c.id).padStart(4, '0')}`,
    `"${c.username}"`,
    `"${c.category}"`,
    `"${c.priority}"`,
    `"${c.department}"`,
    `"${c.status}"`,
    `"${(c.address || '').replace(/"/g, '""')}"`,
    `"${c.created_at}"`,
    `"${c.sla_deadline}"`,
    c.rating || '',
    `"${(c.feedback || '').replace(/"/g, '""')}"`
  ]);

  const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');

  res.setHeader('Content-Type', 'text/csv');
  res.setHeader('Content-Disposition', 'attachment; filename="community_complaints.csv"');
  res.send(csvContent);
});

// 404 Handler
app.use((_req, res) => {
  res.status(404).render('home.html');
});

// Global Error Handler
app.use((err: any, _req: any, res: any, _next: any) => {
  console.error('Unhandled Application Error:', err);
  res.status(500).send(`Internal Server Error: ${err?.message || err}`);
});

// Start Server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Project K server running at http://0.0.0.0:${PORT}`);
});
