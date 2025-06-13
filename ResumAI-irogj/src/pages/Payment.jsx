import React, { useState } from 'react';
import { processPayment } from 'wasp/client/operations';
import { getUserCredits } from 'wasp/client/operations';
import { useQuery } from 'wasp/client/operations';

export default function PaymentPage() {
  const [amount, setAmount] = useState(5);
  const [isProcessing, setIsProcessing] = useState(false);
  const [message, setMessage] = useState('');
  
  const { data: userCredits, refetch } = useQuery(getUserCredits);

  const handlePayment = async () => {
    setIsProcessing(true);
    setMessage('');

    try {
      const result = await processPayment({ amount });
      setMessage(`Successfully added ${result.creditsAdded} credits!`);
      refetch(); // Refresh credits display
    } catch (error) {
      setMessage('Payment failed: ' + error.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const styles = {
    container: {
      maxWidth: '600px',
      margin: '0 auto',
      padding: '2rem',
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      marginTop: '2rem'
    },
    title: {
      fontSize: '2rem',
      fontWeight: 'bold',
      textAlign: 'center',
      marginBottom: '1rem'
    },
    credits: {
      textAlign: 'center',
      fontSize: '1.2rem',
      marginBottom: '2rem',
      padding: '1rem',
      backgroundColor: '#f3f4f6',
      borderRadius: '8px'
    },
    input: {
      width: '100%',
      padding: '0.75rem',
      border: '1px solid #d1d5db',
      borderRadius: '4px',
      fontSize: '1rem',
      marginBottom: '1rem'
    },
    button: {
      width: '100%',
      backgroundColor: '#3b82f6',
      color: 'white',
      padding: '0.75rem',
      border: 'none',
      borderRadius: '4px',
      fontSize: '1rem',
      fontWeight: '600',
      cursor: 'pointer'
    },
    message: {
      padding: '0.75rem',
      borderRadius: '4px',
      marginTop: '1rem',
      textAlign: 'center'
    }
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>Buy Credits</h1>
      
      <div style={styles.credits}>
        Current Credits: {userCredits?.credits || 0}
      </div>

      <div>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '600' }}>
          Amount ($1 = 1 credit):
        </label>
        <input
          type="number"
          min="1"
          value={amount}
          onChange={(e) => setAmount(parseInt(e.target.value) || 1)}
          style={styles.input}
        />
        
        <button
          onClick={handlePayment}
          disabled={isProcessing}
          style={{
            ...styles.button,
            opacity: isProcessing ? 0.5 : 1,
            cursor: isProcessing ? 'not-allowed' : 'pointer'
          }}
        >
          {isProcessing ? 'Processing...' : `Buy ${amount} Credits for $${amount}`}
        </button>

        {message && (
          <div style={{
            ...styles.message,
            backgroundColor: message.includes('Successfully') ? '#d1fae5' : '#fee2e2',
            color: message.includes('Successfully') ? '#065f46' : '#991b1b'
          }}>
            {message}
          </div>
        )}
      </div>
    </div>
  );
}