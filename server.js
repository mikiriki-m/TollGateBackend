const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = 3000;
const TOLL_FEE = 2.00;

// 1. Initialize Firebase Admin SDK
const serviceAccount = require('./serviceAccountKey.json');

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  databaseURL: "https://tollgatebackend-default-rtdb.europe-west1.firebasedatabase.app"
});

const db = admin.database();

// -------------------------------------------------------------
// Toll Gate Processing Endpoint
// -------------------------------------------------------------
app.post('/api/toll/process', async (req, res) => {
  const { uid } = req.body;
  const timestamp = new Date().toISOString();

  console.log(`\n[${timestamp}] Incoming scan for UID: ${uid}`);

  try {
    // 2. Fetch User from Firebase (/users/UID)
    const userRef = db.ref(`users/${uid}`);
    const snapshot = await userRef.once('value');

    if (!snapshot.exists()) {
      console.log(`❌ DENIED: Card UID [${uid}] not found in database.`);
      return res.status(404).json({
        status: "DENIED",
        reason: "CARD_NOT_REGISTERED",
        message: "Card not registered in system."
      });
    }

    const user = snapshot.val();

    // 3. Check Balance
    if (user.balance < TOLL_FEE) {
      console.log(`❌ DENIED: ${user.name} has insufficient funds ($${user.balance.toFixed(2)}).`);
      return res.status(400).json({
        status: "DENIED",
        reason: "INSUFFICIENT_FUNDS",
        message: "Insufficient balance.",
        current_balance: user.balance
      });
    }

    // 4. Calculate New Balance & Update Firebase
    const newBalance = user.balance - TOLL_FEE;
    await userRef.update({ balance: newBalance });

    // 5. Save Transaction Record (/transactions)
    const txRef = db.ref('transactions').push();
    const txRecord = {
      id: txRef.key,
      uid: uid,
      user: user.name,
      amount: TOLL_FEE,
      remaining_balance: newBalance,
      timestamp: timestamp
    };
    await txRef.set(txRecord);

    console.log(`✅ APPROVED: ${user.name} paid $${TOLL_FEE}. New balance: $${newBalance.toFixed(2)}.`);

    return res.status(200).json({
      status: "APPROVED",
      user_name: user.name,
      fee_charged: TOLL_FEE,
      remaining_balance: newBalance
    });

  } catch (error) {
    console.error("Firebase Error:", error);
    return res.status(500).json({ status: "ERROR", message: "Database connection failed" });
  }
});

// Start Server
app.listen(PORT, () => {
  console.log(`=================================`);
  console.log(`Toll Gate Backend Active on Port ${PORT}`);
  console.log(`Connected to Firebase Realtime DB`);
  console.log(`=================================`);
});