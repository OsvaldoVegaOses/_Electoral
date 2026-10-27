import React from 'react';
import { Chip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import LockIcon from '@mui/icons-material/Lock';
import EditIcon from '@mui/icons-material/Edit';
import BlockIcon from '@mui/icons-material/Block';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';

const StatusBadge = ({ status, size = 'small' }) => {
  let icon = null;
  let label = status || 'Desconocido';
  let customSx = {};

  switch (status) {
    case 'Abierta':
      icon = <CheckCircleIcon sx={{ fontSize: 14 }} />;
      customSx = {
        backgroundColor: '#ecfdf5',
        color: '#065f46',
        fontWeight: 700,
        border: '1px solid #a7f3d0',
      };
      break;
    case 'Cerrada':
      icon = <LockIcon sx={{ fontSize: 14 }} />;
      customSx = {
        backgroundColor: '#fffbeb',
        color: '#92400e',
        fontWeight: 700,
        border: '1px solid #fde68a',
      };
      break;
    case 'Finalizada':
      icon = <CheckCircleIcon sx={{ fontSize: 14 }} />;
      customSx = {
        backgroundColor: '#f0fdf4',
        color: '#15803d',
        fontWeight: 700,
        border: '1px solid #bbf7d0',
      };
      break;
    case 'Borrador':
      icon = <EditIcon sx={{ fontSize: 14 }} />;
      customSx = {
        backgroundColor: '#f1f5f9',
        color: '#475569',
        fontWeight: 600,
        border: '1px solid #cbd5e1',
      };
      break;
    case 'Votó':
      icon = <CheckCircleIcon sx={{ fontSize: 14 }} />;
      customSx = {
        backgroundColor: '#ecfdf5',
        color: '#047857',
        fontWeight: 700,
        border: '1px solid #a7f3d0',
      };
      break;
    case 'Pendiente':
      icon = <HourglassEmptyIcon sx={{ fontSize: 14 }} />;
      customSx = {
        backgroundColor: '#eff6ff',
        color: '#1d4ed8',
        fontWeight: 600,
        border: '1px solid #bfdbfe',
      };
      break;
    case 'Bloqueado':
      icon = <BlockIcon sx={{ fontSize: 14 }} />;
      customSx = {
        backgroundColor: '#fef2f2',
        color: '#b91c1c',
        fontWeight: 600,
        border: '1px solid #fecaca',
      };
      break;
    default:
      customSx = {
        backgroundColor: '#f8fafc',
        color: '#64748b',
      };
  }

  return (
    <Chip
      size={size}
      icon={icon}
      label={label}
      sx={{
        borderRadius: '6px',
        fontSize: size === 'small' ? '0.75rem' : '0.85rem',
        ...customSx,
      }}
    />
  );
};

export default StatusBadge;
