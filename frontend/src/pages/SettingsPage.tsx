import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  Button,
  TextField,
  Grid,
  Card,
  CardContent,
  CardActions,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Chip,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Refresh as RefreshIcon,
  Key as KeyIcon,
  Person as PersonIcon,
} from '@mui/icons-material';

import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';

// Interfaces
interface Credential {
  id: number;
  service: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

interface Extension {
  id: number;
  extension_id: string;
  name: string;
  extension_number: string | null;
  type: string | null;
  enabled: boolean;
}

interface LeadOwner {
  id: number;
  zoho_id: string;
  name: string;
  email: string;
  role: string | null;
  is_active: boolean;
}

interface NewCredential {
  service: string;
  name: string;
  value: string;
}

const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<number>(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [newCredential, setNewCredential] = useState<NewCredential>({ service: 'ringcentral', name: '', value: '' });
  const [editCredential, setEditCredential] = useState<{ id: number, value: string }>({ id: 0, value: '' });
  const [deleteCredentialId, setDeleteCredentialId] = useState<number | null>(null);
  
  // Fetch credentials
  const { data: credentials, isLoading: credentialsLoading, error: credentialsError } = useQuery<Credential[]>(
    ['credentials'],
    async () => {
      const response = await api.get('/api/settings/credentials');
      return response.data;
    },
    {
      enabled: user?.is_admin && tab === 0,
    }
  );
  
  // Fetch extensions
  const { data: extensions, isLoading: extensionsLoading, error: extensionsError } = useQuery<Extension[]>(
    ['extensions'],
    async () => {
      const response = await api.get('/api/calls/extensions');
      return response.data;
    },
    {
      enabled: tab === 1,
    }
  );
  
  // Fetch lead owners
  const { data: leadOwners, isLoading: leadOwnersLoading, error: leadOwnersError } = useQuery<LeadOwner[]>(
    ['leadOwners'],
    async () => {
      const response = await api.get('/api/calls/lead-owners');
      return response.data;
    },
    {
      enabled: tab === 2,
    }
  );
  
  // Create credential mutation
  const createCredentialMutation = useMutation(
    async (credential: NewCredential) => {
      const response = await api.post('/api/settings/credentials', credential);
      return response.data;
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['credentials']);
        setDialogOpen(false);
        setNewCredential({ service: 'ringcentral', name: '', value: '' });
      },
    }
  );
  
  // Update credential mutation
  const updateCredentialMutation = useMutation(
    async (credential: { id: number, value: string }) => {
      const response = await api.put(`/api/settings/credentials/${credential.id}`, { value: credential.value });
      return response.data;
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['credentials']);
        setEditDialogOpen(false);
        setEditCredential({ id: 0, value: '' });
      },
    }
  );
  
  // Delete credential mutation
  const deleteCredentialMutation = useMutation(
    async (id: number) => {
      const response = await api.delete(`/api/settings/credentials/${id}`);
      return response.data;
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['credentials']);
        setDeleteDialogOpen(false);
        setDeleteCredentialId(null);
      },
    }
  );
  
  // Sync extensions mutation
  const syncExtensionsMutation = useMutation(
    async () => {
      const response = await api.post('/api/calls/extensions/sync');
      return response.data;
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['extensions']);
      },
    }
  );
  
  // Sync lead owners mutation
  const syncLeadOwnersMutation = useMutation(
    async () => {
      const response = await api.post('/api/calls/lead-owners/sync');
      return response.data;
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['leadOwners']);
      },
    }
  );
  
  // Handle tab change
  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTab(newValue);
  };
  
  // Handle new credential change
  const handleNewCredentialChange = (field: keyof NewCredential) => (e: React.ChangeEvent<HTMLInputElement | { value: unknown }>) => {
    setNewCredential({
      ...newCredential,
      [field]: e.target.value,
    });
  };
  
  // Check if user is admin
  if (!user?.is_admin) {
    return (
      <Box>
        <Typography variant="h4" component="h1" gutterBottom>
          Settings
        </Typography>
        <Alert severity="warning">
          You need administrator privileges to access this page.
        </Alert>
      </Box>
    );
  }
  
  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Settings
      </Typography>
      
      <Paper sx={{ mb: 4 }}>
        <Tabs
          value={tab}
          onChange={handleTabChange}
          indicatorColor="primary"
          textColor="primary"
          centered
        >
          <Tab label="API Credentials" />
          <Tab label="Extensions" />
          <Tab label="Lead Owners" />
        </Tabs>
      </Paper>
      
      {/* API Credentials Tab */}
      {tab === 0 && (
        <Box>
          <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h5" component="h2">
              API Credentials
            </Typography>
            
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setDialogOpen(true)}
            >
              Add Credential
            </Button>
          </Box>
          
          {credentialsLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
              <CircularProgress />
            </Box>
          )}
          
          {credentialsError && (
            <Alert severity="error" sx={{ mb: 4 }}>
              Error loading credentials: {(credentialsError as Error)?.message || 'Unknown error'}
            </Alert>
          )}
          
          {credentials && (
            <Grid container spacing={3}>
              {credentials.map((credential) => (
                <Grid item xs={12} sm={6} md={4} key={credential.id}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6" component="div">
                          {credential.name}
                        </Typography>
                        <Chip 
                          label={credential.service} 
                          color={credential.service === 'ringcentral' ? 'primary' : 'secondary'}
                          size="small" 
                        />
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <KeyIcon fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
                        <Typography variant="body2" color="text.secondary">
                          Value: ••••••••••••••••
                        </Typography>
                      </Box>
                      <Typography variant="body2" color="text.secondary">
                        Created: {new Date(credential.created_at).toLocaleDateString()}
                      </Typography>
                    </CardContent>
                    <CardActions>
                      <IconButton 
                        size="small" 
                        onClick={() => {
                          setEditCredential({ id: credential.id, value: '' });
                          setEditDialogOpen(true);
                        }}
                      >
                        <EditIcon />
                      </IconButton>
                      <IconButton 
                        size="small" 
                        color="error"
                        onClick={() => {
                          setDeleteCredentialId(credential.id);
                          setDeleteDialogOpen(true);
                        }}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </CardActions>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </Box>
      )}
      
      {/* Extensions Tab */}
      {tab === 1 && (
        <Box>
          <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h5" component="h2">
              RingCentral Extensions
            </Typography>
            
            <Button
              variant="contained"
              startIcon={<RefreshIcon />}
              onClick={() => syncExtensionsMutation.mutate()}
              disabled={syncExtensionsMutation.isLoading}
            >
              {syncExtensionsMutation.isLoading ? 'Syncing...' : 'Sync Extensions'}
            </Button>
          </Box>
          
          {extensionsLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
              <CircularProgress />
            </Box>
          )}
          
          {extensionsError && (
            <Alert severity="error" sx={{ mb: 4 }}>
              Error loading extensions: {(extensionsError as Error)?.message || 'Unknown error'}
            </Alert>
          )}
          
          {extensions && (
            <Grid container spacing={3}>
              {extensions.map((extension) => (
                <Grid item xs={12} sm={6} md={4} key={extension.id}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6" component="div">
                          {extension.name}
                        </Typography>
                        <Chip 
                          label={extension.enabled ? 'Enabled' : 'Disabled'} 
                          color={extension.enabled ? 'success' : 'default'}
                          size="small" 
                        />
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <Typography variant="body2" color="text.secondary">
                          Extension: {extension.extension_number || 'N/A'}
                        </Typography>
                      </Box>
                      <Typography variant="body2" color="text.secondary">
                        Type: {extension.type || 'Unknown'}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </Box>
      )}
      
      {/* Lead Owners Tab */}
      {tab === 2 && (
        <Box>
          <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h5" component="h2">
              Zoho Lead Owners
            </Typography>
            
            <Button
              variant="contained"
              color="secondary"
              startIcon={<RefreshIcon />}
              onClick={() => syncLeadOwnersMutation.mutate()}
              disabled={syncLeadOwnersMutation.isLoading}
            >
              {syncLeadOwnersMutation.isLoading ? 'Syncing...' : 'Sync Lead Owners'}
            </Button>
          </Box>
          
          {leadOwnersLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
              <CircularProgress />
            </Box>
          )}
          
          {leadOwnersError && (
            <Alert severity="error" sx={{ mb: 4 }}>
              Error loading lead owners: {(leadOwnersError as Error)?.message || 'Unknown error'}
            </Alert>
          )}
          
          {leadOwners && (
            <Grid container spacing={3}>
              {leadOwners.map((owner) => (
                <Grid item xs={12} sm={6} md={4} key={owner.id}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6" component="div">
                          {owner.name}
                        </Typography>
                        <Chip 
                          label={owner.is_active ? 'Active' : 'Inactive'} 
                          color={owner.is_active ? 'success' : 'default'}
                          size="small" 
                        />
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <PersonIcon fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
                        <Typography variant="body2" color="text.secondary">
                          {owner.email}
                        </Typography>
                      </Box>
                      <Typography variant="body2" color="text.secondary">
                        Role: {owner.role || 'Unknown'}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </Box>
      )}
      
      {/* Add Credential Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
        <DialogTitle>Add API Credential</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Add a new API credential for RingCentral or Zoho.
          </DialogContentText>
          
          <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth>
              <InputLabel id="service-label">Service</InputLabel>
              <Select
                labelId="service-label"
                id="service"
                value={newCredential.service}
                label="Service"
                onChange={handleNewCredentialChange('service')}
              >
                <MenuItem value="ringcentral">RingCentral</MenuItem>
                <MenuItem value="zoho">Zoho</MenuItem>
              </Select>
            </FormControl>
            
            <TextField
              fullWidth
              label="Credential Name"
              value={newCredential.name}
              onChange={handleNewCredentialChange('name')}
              helperText={
                newCredential.service === 'ringcentral' 
                  ? 'E.g., client_id, client_secret, jwt_token, account_id' 
                  : 'E.g., client_id, client_secret, refresh_token'
              }
            />
            
            <TextField
              fullWidth
              label="Credential Value"
              value={newCredential.value}
              onChange={handleNewCredentialChange('value')}
              type="password"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={() => createCredentialMutation.mutate(newCredential)} 
            disabled={createCredentialMutation.isLoading || !newCredential.name || !newCredential.value}
            variant="contained"
          >
            {createCredentialMutation.isLoading ? <CircularProgress size={24} /> : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Edit Credential Dialog */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)}>
        <DialogTitle>Edit API Credential</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Update the value of the selected API credential.
          </DialogContentText>
          
          <Box sx={{ mt: 2 }}>
            <TextField
              fullWidth
              label="New Credential Value"
              value={editCredential.value}
              onChange={(e) => setEditCredential({ ...editCredential, value: e.target.value })}
              type="password"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={() => updateCredentialMutation.mutate(editCredential)} 
            disabled={updateCredentialMutation.isLoading || !editCredential.value}
            variant="contained"
          >
            {updateCredentialMutation.isLoading ? <CircularProgress size={24} /> : 'Update'}
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Delete Credential Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete API Credential</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this API credential? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={() => deleteCredentialId && deleteCredentialMutation.mutate(deleteCredentialId)} 
            disabled={deleteCredentialMutation.isLoading}
            variant="contained"
            color="error"
          >
            {deleteCredentialMutation.isLoading ? <CircularProgress size={24} /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SettingsPage; 