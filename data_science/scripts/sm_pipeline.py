import os
import json
import boto3
import sagemaker
from datetime import datetime, UTC
from sagemaker.session import Session
from sagemaker.workflow.pipeline_context import PipelineSession
from sagemaker.workflow.parameters import ParameterInteger, ParameterFloat, ParameterString
from sagemaker.workflow.steps import ProcessingStep, TuningStep, TrainingStep
from sagemaker.clarify import SageMakerClarifyProcessor, DataConfig, BiasConfig
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.estimator import Estimator
from sagemaker.inputs import TrainingInput
from sagemaker.tuner import IntegerParameter, ContinuousParameter, HyperparameterTuner
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionLessThanOrEqualTo
from sagemaker.workflow.functions import JsonGet
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.properties import PropertyFile

def get_sns_topic_arn():
    region = os.environ["AWS_DEFAULT_REGION"]
    cf = boto3.client('cloudformation', region_name = region)
    response = cf.describe_stacks(StackName="DataScienceStage-SageMakerNotificationStack")
    for output in response['Stacks'][0]['Outputs']:
        if output['OutputKey'] == 'SNSNotificationTopicArn':
            return output['OutputValue']

# Environment Variables
PROJECT_NAME = os.environ["PROJECT_NAME"]
INPUT_DATA = os.environ["INPUT_DATA"]
AWS_DEFAULT_REGION = os.environ["AWS_DEFAULT_REGION"]
ECR_REPOSITORY_URI = os.environ["ECR_REPOSITORY_URI"]
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
SNS_TOPIC_ARN = get_sns_topic_arn()
PROCESSING_INSTANCE_COUNT = int(os.environ["PROCESSING_INSTANCE_COUNT"])
PROCESSING_INSTANCE_TYPE = os.environ["PROCESSING_INSTANCE_TYPE"]
TRAINING_INSTANCE_COUNT = int(os.environ["TRAINING_INSTANCE_COUNT"])
TRAINING_INSTANCE_TYPE = os.environ["TRAINING_INSTANCE_TYPE"]
CLARIFY_INSTANCE_COUNT = int(os.environ["CLARIFY_INSTANCE_COUNT"])
CLARIFY_INSTANCE_TYPE = os.environ["CLARIFY_INSTANCE_TYPE"]
RMSE_THRESHOLD = float(os.environ["RMSE_THRESHOLD"])
MAX_JOBS = int(os.environ["MAX_JOBS"])
MAX_PARALLEL_JOBS = int(os.environ["MAX_PARALLEL_JOBS"])

input_data = INPUT_DATA
data_science_bucket = S3_BUCKET_NAME
region = AWS_DEFAULT_REGION
pipeline_name = f"{PROJECT_NAME}-sagemaker-train-pipeline"
base_job_prefix = f"{PROJECT_NAME}-flights-data"
image_uri = ECR_REPOSITORY_URI
timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")

# Sessions
boto_session = boto3.Session(region_name=region)
sagemaker_client = boto_session.client("sagemaker", region_name=region)
sagemaker_session = sagemaker.Session(boto_session=boto_session, default_bucket=data_science_bucket)
pipeline_session = PipelineSession(boto_session=boto_session, default_bucket=data_science_bucket)
role = os.environ["SAGEMAKER_EXECUTION_ROLE_ARN"]

# Sagemaker Pipeline Parameters
processing_instance_count = ParameterInteger(name="ProcessingInstanceCount", default_value=PROCESSING_INSTANCE_COUNT)
processing_instance_type = ParameterString(name="ProcessingInstanceType", default_value=PROCESSING_INSTANCE_TYPE)
training_instance_count = ParameterInteger(name="TrainingInstanceCount", default_value=TRAINING_INSTANCE_COUNT)
training_instance_type = ParameterString(name="TrainingInstanceType", default_value=TRAINING_INSTANCE_TYPE)
clarify_instance_count = ParameterInteger(name="ClarifyInstanceCount", default_value=CLARIFY_INSTANCE_COUNT)
clarify_instance_type = ParameterString(name="ClarifyInstanceType", default_value=CLARIFY_INSTANCE_TYPE)

# Hyperparameter Tuning Parameters
rmse_threshold = ParameterFloat(name="RMSEThreshold", default_value=RMSE_THRESHOLD)
max_jobs = ParameterInteger(name="MaxJobs", default_value=MAX_JOBS)
max_parallel_jobs = ParameterInteger(name="MaxParallelJobs", default_value=MAX_PARALLEL_JOBS)

sns_topic_arn = ParameterString(name="SnsTopicArn",default_value=SNS_TOPIC_ARN)

# -------------------------------------------
# Step-1: Clarify Pre Training Bias Analysis
# -------------------------------------------

clarify_pre_output_prefix = "sagemaker-clarify-pre-training-output"

clarify_pre_processor = SageMakerClarifyProcessor(
    role=role,
    instance_count=clarify_instance_count,
    instance_type=clarify_instance_type,
    sagemaker_session=pipeline_session,
)

input_source = f"s3://{data_science_bucket}/athena-sample/{input_data}"

pre_training_data_config = DataConfig(
    s3_data_input_path=input_source,
    s3_output_path=f"s3://{data_science_bucket}/{clarify_pre_output_prefix}",
    label="dep_delay",  # Target variable
    headers=[
        "year",
        "month",
        "day",
        "dep_time",
        "sched_dep_time",
        "dep_delay",
        "arr_time",
        "sched_arr_time",
        "arr_delay",
        "carrier",
        "flight",
        "tailnum",
        "origin",
        "dest",
        "air_time",
        "distance",
        "hour",
        "minute",
        "airline",
        "route",
        "temp",
        "dewp",
        "humid",
        "wind_dir",
        "wind_speed",
        "wind_gust",
        "precip",
        "pressure",
        "visib",
        "date",
        "date_string",
    ],
    dataset_type="text/csv",
)

pre_training_bias_config = BiasConfig(
    label_values_or_threshold=[0],
    facet_name="carrier",
    facet_values_or_threshold=["AS", "UA", "DL"],
    group_name="airline",
)

pre_training_clarify_args = clarify_pre_processor.run_pre_training_bias(
    data_config=pre_training_data_config,
    data_bias_config=pre_training_bias_config,
    methods="all",
    job_name=f"{base_job_prefix}-pre-training-bias-{timestamp}",
    wait=False,
    logs=False,
)

clarify_pre_step = ProcessingStep(name="FlightsPreTrainingBiasAnalysis", step_args=pre_training_clarify_args)

# ------------------------------------------------------
# Step 2: Processing Step (Feature Engineering)
# ------------------------------------------------------

input_source = f"s3://{data_science_bucket}/athena-sample/{input_data}"
preprocess_output_prefix = "sagemaker-preprocess-output"

framework_version = "1.2-1"

sklearn_processor = SKLearnProcessor(
    framework_version=framework_version,
    instance_type=processing_instance_type,
    instance_count=processing_instance_count,
    base_job_name=f"{base_job_prefix}-preprocess-{timestamp}",
    role=role,
    sagemaker_session=pipeline_session,
)

processor_args = sklearn_processor.run(
    inputs=[
        ProcessingInput(source=input_source, destination="/opt/ml/processing/input"),
    ],
    outputs=[
        ProcessingOutput(
            output_name="train",
            source="/opt/ml/processing/output/train",
            destination=f"s3://{data_science_bucket}/{preprocess_output_prefix}/train",
        ),
        ProcessingOutput(
            output_name="validation",
            source="/opt/ml/processing/output/validation",
            destination=f"s3://{data_science_bucket}/{preprocess_output_prefix}/validation",
        ),
        ProcessingOutput(
            output_name="test",
            source="/opt/ml/processing/output/test",
            destination=f"s3://{data_science_bucket}/{preprocess_output_prefix}/test",
        ),
        ProcessingOutput(
            output_name="combined",
            source="/opt/ml/processing/output/combined",
            destination=f"s3://{data_science_bucket}/{preprocess_output_prefix}/combined",
        ),
        ProcessingOutput(
            output_name="baseline",
            source="/opt/ml/processing/output/baseline",
            destination=f"s3://{data_science_bucket}/{preprocess_output_prefix}/baseline",
        ),
        ProcessingOutput(
            output_name="drift",
            source="/opt/ml/processing/output/drift",
            destination=f"s3://{data_science_bucket}/{preprocess_output_prefix}/drift",
        ),
    ],
    code="preprocess.py",
)
process_step = ProcessingStep(name="FlightsPreprocessing", step_args=processor_args)

# -------------------------------------
# Step 3: HyperParameter Tuning  Step
# -------------------------------------

hptuning_output_prefix = "sagemaker-hptuning-output"
model_output_path = f"s3://{data_science_bucket}/{hptuning_output_prefix}/model"

xgb_train = Estimator(
    image_uri=image_uri,
    instance_type=training_instance_type,
    instance_count=training_instance_count,
    output_path=model_output_path,
    base_job_name=f"{base_job_prefix}-hptuning-{timestamp}",
    sagemaker_session=pipeline_session,
    role=role,
    use_spot_instances=True,
    max_run=3600,
    max_wait=3600,
)

hyperparameter_ranges = {
    "eta": ContinuousParameter(0.01, 0.1),
    "max_depth": IntegerParameter(2, 4),
    "colsample_bytree": ContinuousParameter(0.5, 1.0),
    "num_round": IntegerParameter(50, 300),
}

objective_metric_name = "validation-rmse"

tuner = HyperparameterTuner(
    estimator=xgb_train,
    objective_metric_name=objective_metric_name,
    hyperparameter_ranges=hyperparameter_ranges,
    metric_definitions=[
        {
            "Name": "validation-rmse",
            "Regex": r"validation-rmse=([0-9\.]+)",
        }
    ],
    objective_type="Minimize",
    max_jobs=max_jobs,
    max_parallel_jobs=max_parallel_jobs,
)

train_path = process_step.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri
validation_path = process_step.properties.ProcessingOutputConfig.Outputs["validation"].S3Output.S3Uri

inputs = {
    "train": TrainingInput(s3_data=train_path, content_type="text/csv"),
    "validation": TrainingInput(s3_data=validation_path, content_type="text/csv"),
}
hpo_args = tuner.fit(inputs)
tuning_step = TuningStep(name="FlightsHyperParameterTuning", step_args=hpo_args, depends_on=[process_step])

# -----------------------------
# Step-4: Final Training Step
# -----------------------------

final_training_output_prefix = "sagemaker-final-training-output"
final_model_output_path = f"s3://{data_science_bucket}/{final_training_output_prefix}/model"

final_estimator = Estimator(
    image_uri=image_uri,
    instance_type=training_instance_type,
    instance_count=training_instance_count,
    output_path=final_model_output_path,
    base_job_name=f"{base_job_prefix}-final-training-{timestamp}",
    sagemaker_session=pipeline_session,
    role=role,
    use_spot_instances=True,
    max_run=3600,
    max_wait=3600,
)

final_estimator.set_hyperparameters(
    colsample_bytree=tuning_step.properties.BestTrainingJob.TunedHyperParameters["colsample_bytree"],
    eta=tuning_step.properties.BestTrainingJob.TunedHyperParameters["eta"],
    max_depth=tuning_step.properties.BestTrainingJob.TunedHyperParameters["max_depth"],
    num_round=tuning_step.properties.BestTrainingJob.TunedHyperParameters["num_round"],
)

combined_train_path = process_step.properties.ProcessingOutputConfig.Outputs["combined"].S3Output.S3Uri

inputs = {
    "train": TrainingInput(s3_data=combined_train_path, content_type="text/csv"),
}

train_args = final_estimator.fit(inputs)
train_step = TrainingStep(
    name="FlightsFinalTraining",
    step_args=train_args,
    depends_on=[tuning_step],
)

# ------------------------------
# Step 5: Model Evaluation Step
# ------------------------------

evaluation_output_prefix = "sagemaker-evaluation-output"
evaluation_output_path = f"s3://{data_science_bucket}/{evaluation_output_prefix}"

script_eval = ScriptProcessor(
    image_uri=image_uri,
    command=["python3"],
    instance_type=processing_instance_type,
    instance_count=processing_instance_count,
    base_job_name=f"{base_job_prefix}-evaluation-{timestamp}",
    role=role,
    sagemaker_session=pipeline_session,
)

eval_args = script_eval.run(
    inputs=[
        ProcessingInput(
            source=train_step.properties.ModelArtifacts.S3ModelArtifacts, destination="/opt/ml/processing/model"
        ),
        ProcessingInput(
            source=process_step.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
            destination="/opt/ml/processing/test",
        ),
    ],
    outputs=[
        ProcessingOutput(
            output_name="evaluation", source="/opt/ml/processing/evaluation", destination=evaluation_output_path
        ),
    ],
    code="evaluate.py",
)

evaluation_report = PropertyFile(name="FlightsEvaluationReport", output_name="evaluation", path="evaluation.json")
evaluate_step = ProcessingStep(
    name="FlightsEvaluateModel", step_args=eval_args, property_files=[evaluation_report], depends_on=[train_step]
)

# ------------------------
# Step-6: Condition Step
# ------------------------

final_evaluated_model_output_prefix = "sagemaker-final-evaluated-approved-model-output"
final_evaluated_model_output = f"s3://{data_science_bucket}/{final_evaluated_model_output_prefix}"

# if evaluation success copy the model to final evaluated model output
success_model_copy_processor = ScriptProcessor(
    image_uri=image_uri,
    command=["python3"],
    instance_type=processing_instance_type,
    instance_count=processing_instance_count,
    base_job_name=f"{base_job_prefix}-success-model-copy-{timestamp}",
    role=role,
    sagemaker_session=pipeline_session,
    env={
        "AWS_REGION": pipeline_session.boto_session.region_name,
        "SNS_TOPIC_ARN": sns_topic_arn,
        "OUTPUT_MODEL_S3_DIR": final_evaluated_model_output,
        "RMSE_THRESHOLD": rmse_threshold.to_string(),
        "PROJECT_NAME": PROJECT_NAME,
    },
)

success_model_copy_args = success_model_copy_processor.run(
    inputs=[
        ProcessingInput(
            source=train_step.properties.ModelArtifacts.S3ModelArtifacts, destination="/opt/ml/processing/input/model"
        ),
        ProcessingInput(
            source=evaluate_step.properties.ProcessingOutputConfig.Outputs["evaluation"].S3Output.S3Uri,
            destination="/opt/ml/processing/input/evaluation",
        ),
    ],
    outputs=[
        ProcessingOutput(
            source="/opt/ml/processing/output/model",
            destination=final_evaluated_model_output,
            output_name="final_model",
        )
    ],
    code="evaluate_success.py",
)

success_model_copy_step = ProcessingStep(
    name="SuccessCopyEvaluatedModel", step_args=success_model_copy_args, depends_on=[evaluate_step]
)

# if evaluation fails, do not copy the model
model_evaluation_fail_processor = ScriptProcessor(
    image_uri=image_uri,
    command=["python3"],
    instance_type=processing_instance_type,
    instance_count=processing_instance_count,
    base_job_name=f"{base_job_prefix}-model-evaluation-failure-{timestamp}",
    role=role,
    sagemaker_session=pipeline_session,
    env={
        "AWS_REGION": pipeline_session.boto_session.region_name,
        "SNS_TOPIC_ARN": sns_topic_arn,
        "RMSE_THRESHOLD": rmse_threshold.to_string(),
    },
)

model_evaluation_fail_args = model_evaluation_fail_processor.run(
    inputs=[
        ProcessingInput(
            source=evaluate_step.properties.ProcessingOutputConfig.Outputs["evaluation"].S3Output.S3Uri,
            destination="/opt/ml/processing/input/evaluation",
        )
    ],
    code="evaluate_failure.py",
)

model_evaluation_fail_step = ProcessingStep(
    name="ModelEvaluationFailure", step_args=model_evaluation_fail_args, depends_on=[evaluate_step]
)

# Condition Step to check RMSE threshold
condition = ConditionLessThanOrEqualTo(
    left=JsonGet(
        step_name=evaluate_step.name, property_file=evaluation_report, json_path="regression_metrics.rmse.value"
    ),
    right=rmse_threshold,
)

condition_step = ConditionStep(
    name="CheckRMSEThreshold",
    conditions=[condition],
    if_steps=[success_model_copy_step],
    else_steps=[model_evaluation_fail_step],
)


# ------------------------
# Trigger the Pipeline Run
# ------------------------

pipeline = Pipeline(
    name=pipeline_name,
    parameters=[
        clarify_instance_type,
        clarify_instance_count,
        processing_instance_count,
        processing_instance_type,
        training_instance_count,
        training_instance_type,
        max_jobs,
        max_parallel_jobs,
        rmse_threshold,
        sns_topic_arn,
    ],
    steps=[
        clarify_pre_step,
        process_step,
        tuning_step,
        train_step,
        evaluate_step,
        condition_step,
    ],
)

pipeline.upsert(role_arn=role)
execution = pipeline.start()
