import React from 'react';
import { Box, Typography } from '@mui/material';

const TheoGenLogo = ({ light = false, compact = false }) => {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, textDecoration: 'none' }}>
      {/* Imagotipo SVG estilizado TheoGen: Escudo cívico y urna digital */}
      <Box
        sx={{
          width: compact ? 34 : 42,
          height: compact ? 34 : 42,
          borderRadius: '10px',
          background: light
            ? 'rgba(255, 255, 255, 0.15)'
            : 'linear-gradient(135deg, #0d233a 0%, #1e40af 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 12px rgba(13, 35, 58, 0.2)',
          border: light ? '1px solid rgba(255, 255, 255, 0.3)' : 'none',
        }}
      >
        <svg
          width={compact ? 20 : 24}
          height={compact ? 20 : 24}
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M12 2L4 5V11.09C4 16.14 7.41 20.85 12 22C16.59 20.85 20 16.14 20 11.09V5L12 2Z"
            fill={light ? '#ffffff' : '#3b82f6'}
            fillOpacity={light ? '0.9' : '0.2'}
            stroke={light ? '#ffffff' : '#38bdf8'}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M9 12L11 14L15 10"
            stroke={light ? '#ffffff' : '#ffffff'}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </Box>

      <Box>
        <Typography
          variant={compact ? 'subtitle1' : 'h6'}
          sx={{
            fontWeight: 800,
            lineHeight: 1.1,
            color: light ? '#ffffff' : '#0d233a',
            letterSpacing: '-0.02em',
          }}
        >
          TheoGen <span style={{ color: light ? '#93c5fd' : '#1e40af', fontWeight: 600 }}>Electoral</span>
        </Typography>
        {!compact && (
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              color: light ? 'rgba(255, 255, 255, 0.7)' : '#64748b',
              fontWeight: 500,
              fontSize: '0.68rem',
              letterSpacing: '0.01em',
            }}
          >
            Participación transparente y verificable
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default TheoGenLogo;
