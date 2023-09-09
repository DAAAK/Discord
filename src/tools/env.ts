import dotenv from 'dotenv';

dotenv.config();

const env = {
  CLIENT_TOKEN: process.env.CLIENT_TOKEN ? process.env.CLIENT_TOKEN : '',
  CLIENT_ID: process.env.CLIENT_ID ? process.env.CLIENT_ID : '',
};

export default env;
