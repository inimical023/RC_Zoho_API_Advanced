import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  CardHeader,
  Button,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  PhoneCallback as AcceptedCallIcon,
  PhoneMissed as MissedCallIcon,
  ImportContacts as LeadsIcon,
  AudioFile as RecordingIcon,
} from '@mui/icons-material';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

import api from '../services/api';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

// Stats interface
interface CallStats {
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  calls: {
    total: number;
    accepted: number;
    missed: number;
    processed: number;
    unprocessed: number;
  };
  leads: {
    created: number;
    with_recordings: number;
  };
}

const DashboardPage: React.FC = () => {
  const [timeRange, setTimeRange] = useState<number>(7);
  
  // Fetch stats data
  const { data, isLoading, isError, error, refetch } = useQuery<CallStats>(
    ['callStats', timeRange],
    async () => {
      const response = await api.get(`/api/calls/stats?days=${timeRange}`);
      return response.data;
    }
  );
  
  // Handle refresh button click
  const handleRefresh = () => {
    refetch();
  };
  
  // Handle time range change
  const handleTimeRangeChange = (event: React.ChangeEvent<{ value: unknown }>) => {
    setTimeRange(event.target.value as number);
  };
  
  // Prepare chart data if stats are available
  const chartData = data ? {
    labels: ['Accepted Calls', 'Missed Calls', 'Processed', 'Unprocessed', 'Leads Created', 'With Recordings'],
    datasets: [
      {
        label: `Last ${timeRange} Days`,
        data: [
          data.calls.accepted,
          data.calls.missed,
          data.calls.processed,
          data.calls.unprocessed,
          data.leads.created,
          data.leads.with_recordings,
        ],
        backgroundColor: [
          'rgba(54, 162, 235, 0.6)',
          'rgba(255, 99, 132, 0.6)',
          'rgba(75, 192, 192, 0.6)',
          'rgba(255, 159, 64, 0.6)',
          'rgba(153, 102, 255, 0.6)',
          'rgba(255, 205, 86, 0.6)',
        ],
        borderColor: [
          'rgb(54, 162, 235)',
          'rgb(255, 99, 132)',
          'rgb(75, 192, 192)',
          'rgb(255, 159, 64)',
          'rgb(153, 102, 255)',
          'rgb(255, 205, 86)',
        ],
        borderWidth: 1,
      },
    ],
  } : null;
  
  // Chart options
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Call Statistics',
      },
    },
  };
  
  return (
    <Box>
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1">
          Dashboard
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2 }}>
          <FormControl sx={{ minWidth: 120 }}>
            <InputLabel id="time-range-label">Time Range</InputLabel>
            <Select
              labelId="time-range-label"
              id="time-range"
              value={timeRange}
              label="Time Range"
              onChange={handleTimeRangeChange}
            >
              <MenuItem value={1}>Last 24 Hours</MenuItem>
              <MenuItem value={7}>Last 7 Days</MenuItem>
              <MenuItem value={30}>Last 30 Days</MenuItem>
              <MenuItem value={90}>Last 90 Days</MenuItem>
            </Select>
          </FormControl>
          
          <Button
            variant="contained"
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            disabled={isLoading}
          >
            Refresh
          </Button>
        </Box>
      </Box>
      
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
          <CircularProgress />
        </Box>
      )}
      
      {isError && (
        <Alert severity="error" sx={{ mb: 4 }}>
          Error loading statistics: {(error as Error)?.message || 'Unknown error'}
        </Alert>
      )}
      
      {data && (
        <>
          {/* Stats Cards */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent sx={{ textAlign: 'center' }}>
                  <AcceptedCallIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
                  <Typography variant="h4" component="div">
                    {data.calls.accepted}
                  </Typography>
                  <Typography color="text.secondary">
                    Accepted Calls
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent sx={{ textAlign: 'center' }}>
                  <MissedCallIcon sx={{ fontSize: 40, color: 'error.main', mb: 1 }} />
                  <Typography variant="h4" component="div">
                    {data.calls.missed}
                  </Typography>
                  <Typography color="text.secondary">
                    Missed Calls
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent sx={{ textAlign: 'center' }}>
                  <LeadsIcon sx={{ fontSize: 40, color: 'success.main', mb: 1 }} />
                  <Typography variant="h4" component="div">
                    {data.leads.created}
                  </Typography>
                  <Typography color="text.secondary">
                    Leads Created
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent sx={{ textAlign: 'center' }}>
                  <RecordingIcon sx={{ fontSize: 40, color: 'warning.main', mb: 1 }} />
                  <Typography variant="h4" component="div">
                    {data.leads.with_recordings}
                  </Typography>
                  <Typography color="text.secondary">
                    With Recordings
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          
          {/* Chart */}
          <Paper sx={{ p: 3, height: 400 }}>
            {chartData && (
              <Bar data={chartData} options={chartOptions} />
            )}
          </Paper>
        </>
      )}
    </Box>
  );
};

export default DashboardPage; 