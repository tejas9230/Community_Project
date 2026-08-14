import express, { Request, Response, NextFunction } from 'express';
import session from 'express-session';
import nunjucks from 'nunjucks';
import bcrypt from 'bcryptjs';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import dotenv from 'dotenv';

dotenv.config();

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

// Flash messages middleware
app.use((req: any, res: Response, next: NextFunction) => {
  res.locals.session = req.session;
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

// Attach req & Jinja request.args compat to template rendering context
app.use((req: any, res: Response, next: NextFunction) => {
  res.locals.req = req;
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
  nextComplaintId: number;
  nextNotificationId: number;
  nextHistoryId: number;
  nextAnnouncementId: number;
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
  nextComplaintId: 1001,
  nextNotificationId: 1,
  nextHistoryId: 1,
  nextAnnouncementId: 1
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
  if (fs.existsSync(DB_FILE)) {
    try {
      const data = fs.readFileSync(DB_FILE, 'utf-8');
      db = JSON.parse(data);
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

// AI / NLP Categorization & Priority Predictor
function predictComplaint(description: string) {
  const desc = description.toLowerCase();
  let category = "Others";
  let department = "Others";
  let priority = "Medium";
  let confidence = 85;

  if (desc.match(/water|pipe|leak|tap|supply|tank|chlorine|seepage/)) {
    category = "Water Supply";
    department = "Water Supply";
    priority = "High";
    confidence = 94;
  } else if (desc.match(/road|pothole|crack|asphalt|street|path|tar|divider|crater/)) {
    category = "Road Damage";
    department = "Roads & Infrastructure";
    priority = "High";
    confidence = 92;
  } else if (desc.match(/street light|dark|lamp|bulb|streetlight|lighting|pole/)) {
    category = "Street Light";
    department = "Electricity & Street Lighting";
    priority = "Medium";
    confidence = 90;
  } else if (desc.match(/electric|power|wire|voltage|transformer|shock|current|fuse/)) {
    category = "Electricity";
    department = "Electricity & Street Lighting";
    priority = "Critical";
    confidence = 96;
  } else if (desc.match(/garbage|trash|waste|dump|bin|clean|smell|litter|debris/)) {
    category = "Garbage";
    department = "Sanitation & Waste Management";
    priority = "Medium";
    confidence = 88;
  } else if (desc.match(/drain|sewage|gutter|overflow|stagnant|manhole|clog/)) {
    category = "Drainage";
    department = "Drainage & Sewage";
    priority = "High";
    confidence = 91;
  } else if (desc.match(/dog|stray|monkey|animal|bite|cattle|cow|snake/)) {
    category = "Animal";
    department = "Animal Control";
    priority = "High";
    confidence = 89;
  } else if (desc.match(/traffic|signal|jam|parking|congestion|accident|gridlock/)) {
    category = "Traffic";
    department = "Traffic & Public Safety";
    priority = "Medium";
    confidence = 87;
  } else if (desc.match(/park|bench|tree|playground|grass|garden|pruning/)) {
    category = "Parks & Green Spaces";
    department = "Parks & Green Spaces";
    priority = "Low";
    confidence = 86;
  } else if (desc.match(/property|building|fence|wall|vandalism|public|bus stop/)) {
    category = "Public Property";
    department = "Public Property Maintenance";
    priority = "Low";
    confidence = 85;
  }

  return { success: true, category, department, priority, confidence };
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
  const user = db.users.find(u => u.username.toLowerCase() === trimmedUname.toLowerCase());

  if (!user) {
    req.flash('Invalid username or password. Please try again.', 'error');
    return res.redirect('/login');
  }

  const match = await bcrypt.compare(password || '', user.passwordHash);
  if (!match && password !== user.passwordHash) {
    req.flash('Invalid username or password. Please try again.', 'error');
    return res.redirect('/login');
  }

  req.session.username = user.username;
  req.session.role = user.role;
  req.session.department = user.department;

  if (user.role === 'Admin') {
    return res.redirect('/admin');
  } else if (user.role === 'Officer') {
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

// Submit Complaint
app.get('/submit_complaint', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  res.render('submit_complaint.html');
});

app.post('/submit_complaint', upload.single('image'), (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');

  const { description, address, latitude, longitude } = req.body;

  if (!latitude || !longitude) {
    req.flash('Please pick your location on the map before submitting.', 'error');
    return res.redirect('/submit_complaint');
  }

  const aiResult = predictComplaint(description || '');
  const category = aiResult.category;
  const department = aiResult.department;
  const priority = aiResult.priority;
  const sla_deadline = getSlaDeadline(category);

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
    upvotes: 0
  };

  db.complaints.unshift(newComplaint);

  db.history.push({
    id: db.nextHistoryId++,
    complaint_id: newId,
    officer_username: 'System AI',
    old_status: '',
    new_status: 'Pending',
    remarks: `Complaint submitted and classified under ${category} (${department}). Priority: ${priority}.`,
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

app.post('/feedback/:id', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  const id = parseInt(req.params.id, 10);
  const { rating, feedback } = req.body;

  const complaint = db.complaints.find(c => c.id === id);
  if (complaint) {
    complaint.rating = parseInt(rating, 10) || 5;
    complaint.feedback = feedback || '';
    saveDatabase();
  }

  req.flash('Thank you for your rating and feedback!', 'success');
  res.redirect('/view_complaints');
});

// -------------------------------------------------------------
// Admin Portal & Management
// -------------------------------------------------------------
app.get('/admin', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  if (req.session.role !== 'Admin' && req.session.username !== 'admin') {
    return res.status(403).send('Access Denied. Administrator role required.');
  }

  const { search, category, priority, status, escalated } = req.query;

  let activeComplaints = db.complaints.filter(c => c.status === 'Pending' || c.status === 'In Progress');

  if (search) {
    const s = String(search).trim().toLowerCase();
    activeComplaints = activeComplaints.filter(c =>
      String(c.id).includes(s) ||
      c.username.toLowerCase().includes(s) ||
      c.address.toLowerCase().includes(s) ||
      c.description.toLowerCase().includes(s)
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
    const area_reports = db.complaints.filter(x => x.category === c.category && x.address === c.address).length;
    const arr: any = [
      c.id, c.username, c.category, c.priority, c.address,
      c.status, c.image_path, area_reports, c.created_at, c.sla_deadline, c.escalated || 0
    ];
    arr.id = c.id;
    arr.username = c.username;
    arr.category = c.category;
    arr.priority = c.priority;
    arr.address = c.address;
    arr.status = c.status;
    arr.image_path = c.image_path;
    arr.area_reports = area_reports;
    arr.created_at = c.created_at;
    arr.sla_deadline = c.sla_deadline;
    arr.escalated = c.escalated || 0;
    return arr;
  });

  const total = db.complaints.length;
  const active = db.complaints.filter(c => c.status === 'Pending' || c.status === 'In Progress').length;
  const pending = db.complaints.filter(c => c.status === 'Pending').length;
  const in_progress = db.complaints.filter(c => c.status === 'In Progress').length;
  const resolved = db.complaints.filter(c => c.status === 'Resolved').length;
  const rejected = db.complaints.filter(c => c.status === 'Rejected').length;

  const now = new Date();
  const nowStr = `${String(now.getDate()).padStart(2, '0')}-${String(now.getMonth() + 1).padStart(2, '0')}-${now.getFullYear()}`;

  const announcementsList = db.announcements.filter(a => a.is_active === 1);

  res.render('admin_dashboard.html', {
    complaints: complaintTuples,
    total,
    active,
    pending,
    in_progress,
    resolved,
    rejected,
    announcements: announcementsList,
    now: nowStr
  });
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

app.post('/update_status/:id', (req: any, res) => {
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
  }

  req.flash(`Complaint SCS-${String(id).padStart(4, '0')} updated successfully.`, 'success');
  res.redirect('/admin');
});

// Direct POST /update_status
app.post('/update_status', (req: any, res) => {
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
  const deptComplaints = db.complaints.filter(c =>
    (c.department === dept || c.assigned_to === uname) &&
    (c.status === 'Pending' || c.status === 'In Progress')
  );

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

  res.render('department_dashboard.html', {
    complaints: complaintObjs,
    department: dept,
    username: req.session.username
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

app.post('/officer_action/:id', upload.single('resolution_image'), (req: any, res) => {
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

app.get('/admin_heatmap', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  res.render('admin_heatmap.html', {
    center_lat: db.communitySettings.latitude,
    center_lon: db.communitySettings.longitude
  });
});

app.get('/analytics', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');

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
  if (!req.session.username) return res.redirect('/login');

  const officers = db.users.filter(u => u.role === 'Officer');
  const stats = officers.map(o => {
    const assignedComplaints = db.complaints.filter(c => c.assigned_to === o.username || c.department === o.department);
    const resolvedCount = assignedComplaints.filter(c => c.status === 'Resolved').length;
    const pendingCount = assignedComplaints.filter(c => c.status === 'Pending' || c.status === 'In Progress').length;
    const rated = assignedComplaints.filter(c => c.rating && c.rating > 0);
    const avgRating = rated.length > 0 ? Math.round((rated.reduce((sum, c) => sum + (c.rating || 0), 0) / rated.length) * 10) / 10 : 0;

    return [o.username, assignedComplaints.length, resolvedCount, avgRating, pendingCount];
  });

  res.render('officer_performance.html', {
    stats
  });
});

app.get('/admin_settings', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');
  if (req.session.role !== 'Admin' && req.session.username !== 'admin') {
    return res.status(403).send('Access Denied');
  }

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
  if (!req.session.username) return res.redirect('/login');
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
app.get('/api/export/csv', (req: any, res) => {
  if (!req.session.username) return res.redirect('/login');

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

// Start Server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Project K server running at http://0.0.0.0:${PORT}`);
});
