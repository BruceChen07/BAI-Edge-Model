import { useState } from "react";
import {
  Button,
  Form,
  Input,
  Modal,
  Upload,
  Typography,
  message as antdMessage,
} from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { Locale } from "../../i18n/messages";
import { messages } from "../../i18n/messages";
import { api, type ModelInfo } from "../../services/api";
import { extractRcFilesFromUploadList } from "../../utils/uploadFiles";
import {
  getUploadAcceptAttribute,
  prepareFileForUpload,
  validateUploadCandidate,
} from "../../utils/uploadPolicy";
import type { UploadFile } from "antd/es/upload/interface";

const { Paragraph } = Typography;

type CreateKnowledgeBaseModalProps = {
  locale: Locale;
  open: boolean;
  activeModel?: ModelInfo;
  onClose: () => void;
  onCreated?: (kbId: string, kbName: string) => void;
};

export function CreateKnowledgeBaseModal({
  locale,
  open,
  activeModel,
  onClose,
  onCreated,
}: CreateKnowledgeBaseModalProps) {
  const [form] = Form.useForm();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const queryClient = useQueryClient();
  const copy = messages[locale];

  const createMutation = useMutation({
    mutationFn: async (payload: {
      name: string;
      description?: string;
      files: File[];
    }) => {
      const knowledgeBase = await api.createKnowledgeBase({
        name: payload.name,
        description: payload.description,
      });
      for (const file of payload.files) {
        await api.uploadKnowledgeBaseFile({
          kbId: knowledgeBase.id,
          file,
          enableOcr: true,
          modelName: activeModel?.name,
        });
      }
      return knowledgeBase;
    },
    onSuccess: (kb) => {
      antdMessage.success(`${kb.name} created successfully.`);
      form.resetFields();
      setFileList([]);
      onClose();
      onCreated?.(kb.id, kb.name);
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: (error: Error) => {
      antdMessage.error(error.message);
    },
  });

  const handleOk = async () => {
    const values = await form.validateFields();
    const files = extractRcFilesFromUploadList(fileList);
    if (files.length === 0) {
      antdMessage.warning(copy.chat.uploadFiles);
      return;
    }
    const preparedFiles: File[] = [];
    for (const file of files) {
      const prepared = await prepareFileForUpload({
        file,
        model: activeModel,
      });
      if (!prepared.ok) {
        handleValidationFailure(prepared.message, prepared.code);
        return;
      }
      preparedFiles.push(prepared.file);
    }
    await createMutation.mutateAsync({
      name: values.name,
      description: values.description,
      files: preparedFiles,
    });
  };

  const handleCancel = () => {
    form.resetFields();
    setFileList([]);
    onClose();
  };

  const handleValidationFailure = (
    message: string,
    code?: "MODEL_UNSUPPORTED" | "INVALID_EXTENSION" | "FILE_TOO_LARGE",
  ) => {
    if (code === "MODEL_UNSUPPORTED") {
      Modal.warning({
        title: "当前模型不支持文件上传",
        content: message,
        okText: "我知道了",
      });
      return;
    }
    antdMessage.error(message);
  };

  return (
    <Modal
      title={copy.chat.createKnowledgeBaseTitle}
      open={open}
      onCancel={handleCancel}
      onOk={() => void handleOk()}
      okText={copy.chat.submitKnowledgeBase}
      confirmLoading={createMutation.isPending}
      destroyOnHidden
    >
      <Form layout="vertical" form={form}>
        <Form.Item
          label={copy.chat.knowledgeBaseName}
          name="name"
          rules={[{ required: true, message: copy.chat.knowledgeBaseName }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          label={copy.chat.knowledgeBaseDescription}
          name="description"
        >
          <Input.TextArea rows={3} />
        </Form.Item>
        <Form.Item label={copy.chat.uploadFiles}>
          <Upload
            multiple
            fileList={fileList}
            accept={getUploadAcceptAttribute()}
            beforeUpload={(file) => {
              const validation = validateUploadCandidate({
                file,
                model: activeModel,
              });
              if (!validation.ok) {
                handleValidationFailure(validation.message ?? "", validation.code);
                return Upload.LIST_IGNORE;
              }
              setFileList((current) => [...current, file]);
              return false;
            }}
            onRemove={(file) => {
              setFileList((current) =>
                current.filter((item) => item.uid !== file.uid),
              );
            }}
          >
            <Button>{copy.chat.uploadFiles}</Button>
          </Upload>
          <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
            {copy.chat.uploadHint}
          </Paragraph>
        </Form.Item>
      </Form>
    </Modal>
  );
}
