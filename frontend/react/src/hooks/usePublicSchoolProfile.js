import { useEffect, useState } from 'react';
import axios from 'axios';

export default function usePublicSchoolProfile(schoolId) {
  const [schoolProfile, setSchoolProfile] = useState(null);
  const [loadingSchoolProfile, setLoadingSchoolProfile] = useState(true);
  const [schoolProfileError, setSchoolProfileError] = useState('');

  useEffect(() => {
    let mounted = true;
    if (!schoolId) {
      setSchoolProfile(null);
      setLoadingSchoolProfile(false);
      return () => {
        mounted = false;
      };
    }

    const fetchSchoolProfile = async () => {
      setLoadingSchoolProfile(true);
      try {
        const response = await axios.get(`/api/public/schools/${schoolId}/profile`);
        if (mounted) {
          setSchoolProfile(response.data);
          setSchoolProfileError('');
        }
      } catch (error) {
        if (mounted) {
          setSchoolProfile(null);
          setSchoolProfileError(error.response?.data?.message || 'Unable to load school profile.');
        }
      } finally {
        if (mounted) {
          setLoadingSchoolProfile(false);
        }
      }
    };

    fetchSchoolProfile();
    return () => {
      mounted = false;
    };
  }, [schoolId]);

  return { schoolProfile, loadingSchoolProfile, schoolProfileError };
}