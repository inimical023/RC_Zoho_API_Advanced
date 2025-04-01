import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Box,
  Button,
  Typography,
  Paper,
  Tabs,
  Tab,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Chip,
} from '@mui/material';
import { DataGrid, GridColDef, GridValueGetterParams } from '@mui/x-data-grid';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { 
  Refresh as RefreshIcon, 
  Send as SendIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';

import api from '../services/api';

// Interfaces
interface CallRecord {
  id: number;
  rc_call_id: string;
  extension_id: string;
  call_type: string;
  direction: string;
  caller_number: string;
  caller_name: string | null;
  start_time: string;
  end_time: string | null;
  duration: number | null;
  recording_id: string | null;
  recording_url: string | null;
  processed: boolean;
  processing_time: string | null;
  created_at: string;
  updated_at: string | null;
}

const CallLogPage: React.FC = () => {
  const [tab, setTab] = useState<string>('all');
  const [startDate, setStartDate] = useState<Date | null>(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)); // 7 days ago
  const [endDate, setEndDate] = useState<Date | null>(new Date());
  const [showFetchDialog, setShowFetchDialog] = useState(false);
  const [showProcessDialog, setShowProcessDialog] = useState(false);
  
  // Fetch call logs
  const { data: calls, isLoading, error, refetch } = useQuery<CallRecord[]>(
    ['callLogs', tab],
    async () => {
      const params: any = { limit: 100 };
      if (tab !== 'all') {
        params.call_type = tab;
      }
      const response = await api.get('/api/calls/recent', { params });
      return response.data;
    }
  );
  
  // Fetch calls mutation
  const fetchCallsMutation = useMutation(
    async () => {
      if (!startDate || !endDate) return null;
      
      const payload = {
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
      };
      
      const response = await api.post('/api/calls/fetch', payload);
      return response.data;
    },
    {
      onSuccess: () => {
        setShowFetchDialog(false);
        refetch();
      },
    }
  );
  
  // Process calls mutation
  const processCallsMutation = useMutation(
    async () => {
      const response = await api.post('/api/calls/process');
      return response.data;
    },
    {
      onSuccess: () => {
        setShowProcessDialog(false);
        refetch();
      },
    }
  );
  
  // Handle tab change
  const handleTabChange = (_: React.SyntheticEvent, newValue: string) => {
    setTab(newValue);
  };
  
  // Column definitions for the data grid
  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    { 
      field: 'call_type', 
      headerName: 'Type', 
      width: 120,
      renderCell: (params) => (
        <Chip 
          label={params.value} 
          color={params.value === 'Accepted' ? 'primary' : 'error'} 
          size="small" 
        />
      ),
    },
    { field: 'caller_number', headerName: 'Caller Number', width: 150 },
    { field: 'caller_name', headerName: 'Caller Name', width: 180 },
    { 
      field: 'start_time', 
      headerName: 'Start Time', 
      width: 180,
      valueGetter: (params: GridValueGetterParams) => {
        return params.value ? format(new Date(params.value), 'MM/dd/yyyy HH:mm:ss') : '';
      },
    },
    { 
      field: 'duration', 
      headerName: 'Duration', 
      width: 100,
      valueGetter: (params: GridValueGetterParams) => {
        return params.value ? `${params.value}s` : '';
      },
    },
    { 
      field: 'recording_id', 
      headerName: 'Recording', 
      width: 100,
      renderCell: (params) => (
        params.value ? <DownloadIcon color="primary" /> : null
      ),
    },
    { 
      field: 'processed', 
      headerName: 'Processed', 
      width: 120,
      renderCell: (params) => (
        <Chip 
          label={params.value ? 'Yes' : 'No'} 
          color={params.value ? 'success' : 'default'} 
          size="small" 
        />
      ),
    },
  ];
  
  return (
    <Box>
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1">
          Call Logs
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => refetch()}
            disabled={isLoading}
          >
            Refresh
          </Button>
          
          <Button
            variant="contained"
            color="primary"
            startIcon={<DownloadIcon />}
            onClick={() => setShowFetchDialog(true)}
          >
            Fetch Calls
          </Button>
          
          <Button
            variant="contained"
            color="secondary"
            startIcon={<SendIcon />}
            onClick={() => setShowProcessDialog(true)}
          >
            Process Calls
          </Button>
        </Box>
      </Box>
      
      <Paper sx={{ mb: 4 }}>
        <Tabs
          value={tab}
          onChange={handleTabChange}
          indicatorColor="primary"
          textColor="primary"
          centered
        >
          <Tab label="All Calls" value="all" />
          <Tab label="Accepted Calls" value="Accepted" />
          <Tab label="Missed Calls" value="Missed" />
        </Tabs>
      </Paper>
      
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
          <CircularProgress />
        </Box>
      )}
      
      {error && (
        <Alert severity="error" sx={{ mb: 4 }}>
          Error loading call logs: {(error as Error)?.message || 'Unknown error'}
        </Alert>
      )}
      
      {calls && (
        <Paper sx={{ height: 600, width: '100%' }}>
          <DataGrid
            rows={calls}
            columns={columns}
            initialState={{
              pagination: {
                paginationModel: { page: 0, pageSize: 25 },
              },
              sorting: {
                sortModel: [{ field: 'start_time', sort: 'desc' }],
              },
            }}
            pageSizeOptions={[25, 50, 100]}
            checkboxSelection={false}
            disableRowSelectionOnClick
          />
        </Paper>
      )}
      
      {/* Fetch Calls Dialog */}
      <Dialog open={showFetchDialog} onClose={() => setShowFetchDialog(false)}>
        <DialogTitle>Fetch Call Logs</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Select a date range to fetch call logs from RingCentral.
          </DialogContentText>
          
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
              <DateTimePicker
                label="Start Date"
                value={startDate}
                onChange={(newValue) => setStartDate(newValue)}
              />
              
              <DateTimePicker
                label="End Date"
                value={endDate}
                onChange={(newValue) => setEndDate(newValue)}
              />
            </Box>
          </LocalizationProvider>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowFetchDialog(false)}>Cancel</Button>
          <Button 
            onClick={() => fetchCallsMutation.mutate()} 
            disabled={fetchCallsMutation.isLoading || !startDate || !endDate}
            variant="contained"
          >
            {fetchCallsMutation.isLoading ? <CircularProgress size={24} /> : 'Fetch'}
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Process Calls Dialog */}
      <Dialog open={showProcessDialog} onClose={() => setShowProcessDialog(false)}>
        <DialogTitle>Process Calls</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will process all unprocessed calls and create leads in Zoho CRM. Continue?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowProcessDialog(false)}>Cancel</Button>
          <Button 
            onClick={() => processCallsMutation.mutate()} 
            disabled={processCallsMutation.isLoading}
            variant="contained"
            color="secondary"
          >
            {processCallsMutation.isLoading ? <CircularProgress size={24} /> : 'Process'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CallLogPage; 