import React from "react";
import { Box, Typography, Button, AppBar, Toolbar } from "@mui/material";
import { Login as LoginIcon } from "@mui/icons-material";
import { redirectToLogin } from "../utils/auth";

export default function LoginButton() {
  return (
    <Box sx={{ minHeight: '100vh', backgroundColor: '#f5f5f5' }}>
      {/* Same navbar as the app, but no controls */}
      <AppBar position="fixed" elevation={2}>
        <Toolbar sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            VSWIR Plants
          </Typography>
        </Toolbar>
      </AppBar>

      <Toolbar />

      {/* Centered login card */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 'calc(100vh - 64px)',
          px: 2,
        }}
      >
        <Box
          sx={{
            background: 'white',
            borderRadius: 2,
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            borderLeft: '4px solid #1976d2',
            p: 5,
            maxWidth: 400,
            width: '100%',
            textAlign: 'center',
          }}
        >
          {/* Icon */}
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: '50%',
              backgroundColor: '#e3f2fd',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mx: 'auto',
              mb: 2,
            }}
          >
            <LoginIcon sx={{ color: '#1976d2', fontSize: 28 }} />
          </Box>

          <Typography variant="h5" sx={{ fontWeight: 600, mb: 1, color: '#1a1a1a' }}>
            VSWIR Plants
          </Typography>

          <Typography variant="body2" sx={{ color: '#666', mb: 4 }}>
            Sign in to access plant spectral data and analysis tools.
          </Typography>

          <Button
            variant="contained"
            size="large"
            onClick={redirectToLogin}
            startIcon={<LoginIcon />}
            fullWidth
            sx={{
              textTransform: 'none',
              fontWeight: 600,
              py: 1.5,
              fontSize: '1rem',
              backgroundColor: '#1976d2',
              '&:hover': { backgroundColor: '#1565c0' },
            }}
          >
            Sign in with VSWIR Plants SSO
          </Button>
        </Box>
      </Box>
    </Box>
  );
}
