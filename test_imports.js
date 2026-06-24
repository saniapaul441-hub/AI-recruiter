const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const multer = require('multer');
const { createClient } = require('@supabase/supabase-js');
const pdfParse = require('pdf-parse');
const mammoth = require('mammoth');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

console.log('All Node.js Express & Supabase modules loaded successfully!');
console.log('- express:', typeof express === 'function' ? 'OK' : 'FAIL');
console.log('- cors:', typeof cors === 'function' ? 'OK' : 'FAIL');
console.log('- supabase-js:', typeof createClient === 'function' ? 'OK' : 'FAIL');
console.log('- pdf-parse:', typeof pdfParse === 'function' ? 'OK' : 'FAIL');
console.log('- mammoth:', typeof mammoth === 'object' ? 'OK' : 'FAIL');
console.log('- bcryptjs:', typeof bcrypt === 'object' ? 'OK' : 'FAIL');
console.log('- jsonwebtoken:', typeof jwt === 'object' ? 'OK' : 'FAIL');
