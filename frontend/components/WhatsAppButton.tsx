'use client';

export default function WhatsAppButton() {
  return (
    <div 
      id="whatsapp-toggle" 
      style={{
        position: 'fixed', 
        bottom: 20, 
        right: 20, 
        zIndex: 1000
      }}
    >
      <a
        href="https://wa.me/14155238886?text=Hello%2C%20I%20need%20help%20checking%20misinformation."
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: 'inline-block',
          backgroundColor: '#25D366',
          color: 'white',
          borderRadius: '50%',
          width: 60,
          height: 60,
          textAlign: 'center',
          lineHeight: '60px',
          fontSize: 24,
          textDecoration: 'none',
          boxShadow: '0 4px 8px rgba(0,0,0,0.3)',
          transition: 'all 0.3s ease'
        }}
        onMouseOver={(e) => {
          e.currentTarget.style.backgroundColor = '#128C7E';
          e.currentTarget.style.transform = 'scale(1.1)';
        }}
        onMouseOut={(e) => {
          e.currentTarget.style.backgroundColor = '#25D366';
          e.currentTarget.style.transform = 'scale(1)';
        }}
      >
        💬
      </a>
    </div>
  );
}
