#ifndef HEMELB_UNITTESTS_LBTESTS_BOUNDARIES_IOLETS_INOUTLETTESTS_H
#define HEMELB_UNITTESTS_LBTESTS_BOUNDARIES_IOLETS_INOUTLETTESTS_H
#include <cppunit/TestFixture.h>
#include <cppunit/extensions/HelperMacros.h>

#include "lb/boundaries/iolets/InOutLets.h"
#include "resources/Resource.h"

namespace hemelb
{
  namespace unittests
  {
    namespace lbtests
    {
      namespace boundaries
      {
        namespace iolets
        {
          using namespace lb::boundaries::iolets;
          using namespace resources;
          /**
           * Class to test the collision operators. These tests are for the functions involved in
           * calculating the post-collision values, specifically CalculatePreCollision and Collide.
           * For each collision operator, we test that these functions return the expected values of
           * hydrodynamic quantities and f-distribution values.
           *
           * Note that we are only testing collision operators here, so we
           * can assume that the kernel objects work perfectly.
           */
          class InOutLetTests : public CppUnit::TestFixture
          {
            CPPUNIT_TEST_SUITE(InOutLetTests);
                CPPUNIT_TEST(TestCosineConstruct);
              CPPUNIT_TEST_SUITE_END();
            public:
              void setUp()
              {

              }
              void tearDown()
              {

              }
            private:
              void TestCosineConstruct()
              {
                /*
                 * <inlet>
                 <pressure amplitude="0.0" mean="80.1" phase="0.0" period="0.6"/>
                 <normal x="0.0" y="0.0" z="1.0" />
                 <position x="-1.66017717834e-05" y="-4.58437586355e-05" z="-0.05" />
                 </inlet>
                 */
                configuration::SimConfig *config =
                    configuration::SimConfig::Load(Resource("config.xml").Path().c_str());
                lb::SimulationState state = lb::SimulationState(config->TimeStepLength, config->TotalTimeSteps);
                double voxel_size = 0.0001;
                lb::LbmParameters lbmParams = lb::LbmParameters(state.GetTimeStepLength(), voxel_size);
                util::UnitConverter converter = util::UnitConverter(&lbmParams, &state, voxel_size);
                cosine = static_cast<InOutLetCosine*>(config->Inlets[0]);
                CPPUNIT_ASSERT_EQUAL(80.1, cosine->PressureMeanPhysical);
                CPPUNIT_ASSERT_EQUAL(0.0, cosine->PressureAmpPhysical);
                CPPUNIT_ASSERT_EQUAL(0.0, cosine->Phase);
                CPPUNIT_ASSERT_EQUAL(util::Vector3D<float>(-1.66017717834e-05,-4.58437586355e-05,-0.05), cosine->Position);
                CPPUNIT_ASSERT_EQUAL(util::Vector3D<float>(0.0,0.0,1.0), cosine->Normal);

                // at this stage, Initialise() has not been called, so the unit converter will be invalid, so we will not be able to convert to physical units.
                cosine->Initialise(&converter);
                // The min and max are NOT set for cosine values currently, expect problems with steering code.
                double temp = state.GetTimeStepLength() / voxel_size;
                double targetMeanDensity = 1+(80.1 - REFERENCE_PRESSURE_mmHg) * mmHg_TO_PASCAL * temp * temp / (Cs2*BLOOD_DENSITY_Kg_per_m3);
                CPPUNIT_ASSERT_EQUAL(targetMeanDensity, cosine->GetDensityMean());
                std::vector<distribn_t> densitiesBuffer;
                cosine->InitialiseCycle(densitiesBuffer, &state);
                CPPUNIT_ASSERT_EQUAL(1, static_cast<int>(densitiesBuffer.size()));
                CPPUNIT_ASSERT_EQUAL(targetMeanDensity, densitiesBuffer[0]);
              }
              InOutLetCosine *cosine;
          };
          CPPUNIT_TEST_SUITE_REGISTRATION(InOutLetTests);
        }
      }
    }
  }
}

#endif // HEMELB_UNITTESTS_LBTESTS_BOUNDARIES_IOLETS_INOUTLETTESTS_H
