import PaymentInstructions from '../components/PaymentInstructions';

function FeesPage() {
  const currentStudent = { student_code: 'S002', name: 'Abena Selorm' };

  return (
    <div>
      <h1>Pay for {currentStudent.name}</h1>
      {/* Passing the data into the component */}
      <PaymentInstructions 
        student={currentStudent} 
        amount={5.00} 
        type="feeding" 
      />
    </div>
  );
}