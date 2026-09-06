import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const normalizeClassList = (data) => {
  if (!Array.isArray(data)) {
    return [];
  }

  return Array.from(
    new Set(
      data
        .map((item) => {
          if (typeof item === 'string') {
            return item.trim();
          }
          return String(item?.class_name || item?.name || '').trim();
        })
        .filter(Boolean)
    )
  ).sort((left, right) => left.localeCompare(right));
};

export default function useSchoolClasses() {
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);

  const headers = useMemo(() => ({
    Authorization: `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id'),
  }), []);

  const refreshClasses = useCallback(async () => {
    try {
      const response = await axios.get('/api/school/classes', { headers });
      setClasses(normalizeClassList(response.data));
    } catch (error) {
      setClasses([]);
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => {
    refreshClasses();
  }, [refreshClasses]);

  return {
    classes,
    loading,
    refreshClasses,
  };
}