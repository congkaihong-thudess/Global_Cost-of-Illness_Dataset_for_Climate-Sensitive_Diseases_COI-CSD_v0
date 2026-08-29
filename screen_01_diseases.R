#Prepare for working
lapply(c("dplyr","purrr","stringr","readr","readxl","tidyr","httr","jsonlite","glue"),library,character.only=1)

Path<-".../first screening"
api_key<-"...."   #API password

#test DeepSeek API
test_api_functionality<-function(api_key){
  response<-POST(
    "https://api.deepseek.com/v1/chat/completions",
    add_headers(Authorization=paste("Bearer",api_key)),
    content_type("application/json"),
    body=toJSON(list(
      model="deepseek-chat",
      messages=list(list(
        role="user",
        content="Please answer: is DeepSeek API working normally?"
      )),
      temperature=0.3
    ),auto_unbox=TRUE),
    timeout(10)
  )
  if(status_code(response)==200){
    content_raw<-content(response,"text",encoding="UTF-8")
    content_list<-fromJSON(content_raw,simplifyVector=FALSE)
    reply<-content_list$choices[[1]]$message$content
    return(paste("API is normal！Response reply:",reply))
  } else {
    return(paste("API call failed, status code:", 
                 status_code(response),
                 "\n response text:", 
                 content(response,"text",encoding="UTF-8")))
  }
}
test_api_functionality(api_key)


#Start to work
#1.Read all files and eliminate duplicates
output_path<-file.path(Path,"source files/")
merged_files<-list.files(path=output_path,pattern="^original_literature_\\d+\\.xls$",full.names=TRUE)

all_data<-list()

for(file in merged_files){
  df<-read_excel(file)
  file_num<-str_extract(basename(file),"\\d+")
  df<-df %>% mutate(source_files=file_num)
  df[]<-lapply(df,as.character)
  all_data[[file_num]]<-df
}
combined<-bind_rows(all_data)

savedrecs_keep<-c(
  "DOI","Title","Abstract","Source","source_files"
)
combined<-combined %>% select(any_of(savedrecs_keep))
combined<-combined %>% filter(!is.na(DOI) & DOI!="")

combined_final<-combined %>%
  group_by(DOI) %>%
  summarize(
    across(everything(),~paste(unique(na.omit(.x)),collapse="; ")),
    source_files=paste(sort(unique(source_files)),collapse=","),
    .groups="drop")

output_path<-file.path(Path,"Result/merged_all.csv")
write_csv(combined_final,output_path)


#2.Test mode setting and data preprocess
preprocess_data<-function(input_file){
  data<-read.csv(input_file,stringsAsFactors=FALSE,encoding="UTF-8") %>%
  select(DOI,Abstract) %>%  
  mutate(Abstract=str_replace_all(Abstract,"\\s+"," ")) %>%  
  filter(!is.na(Abstract),nchar(Abstract)>50) 
}


#3.Functions for reading data and calling DeepSeek API, for processing individual articles
output_path<-file.path(Path,"Result/merged_all.csv")
data<-preprocess_data(output_path)

output_error<-file.path(Path,"Result/api_error_log.txt")  
output_temp<-file.path(Path,"Result/temp_results.csv")  
output_batch<-file.path(Path,"Result/results_batch_%d.csv") 

classify_abstract<-function(DOI,Abstract,api_key){
  #Prompt
  prompt <- sprintf(
"Please analyze the following abstract to accurately identify whether the literature mentions any climate-sensitive diseases, and conducts some research, analysis, or discussion on them. In order to determine whether the literature should be included, excluded, or remains unclear.

The climate sensitive diseases that need to be identified are divided into two categories, namely climate-sensitive communicable diseases and climate-sensitive non-communicable diseases.
A total of 42 types of climate-sensitive communicable diseases need to be identified, including: cholera; typhoid; paratyphoid; salmonella infection; dysentery; shigellosis; bacterial intestinal infection; e. coli infection; norwalk virus; other intestinal infection; respiratory tuberculosis; pulmonary tuberculosis; zoonotic bacterial disease; plague; anthrax; leptospirosis; relapsing fever; lyme disease; rickettsiosis; typhus; tsutsugamushi; spotted fever; q fever; mosquito-borne viral encephalitis; japanese encephalitis; tick-borne viral encephalitis; arthropod-borne viral fever and viral hemorrhagic fever; dengue; chikungunya; west nile virus; zika virus; yellow fever; hemorrhagic fever with renal syndrome (HFRS); hantavirus (HTV); hepatitis A; viral conjunctivitis; hantavirus pulmonary syndrome (HPS); malaria; leishmaniasis; babesiosis; schistosomiasis; seasonal influenza and pneumonia.
A total of 47 types of climate-sensitive non-communicable diseases need to be identified, including: diabetes; diabetes mellitus; malnutrition; nutritional deficiency; obesity; dementia; mood disorder; mania; depression; anxiety; alzheimer’s disease; cardiovascular disease; hypertension; ischemic heart disease; myocardial infarction; pulmonary embolism; arrhythmia; atrial fibrillation and flutter; heart failure; other cardiovascular disease; cerebrovascular disease; stroke; hemorrhagic stroke; cerebral infarction; other cerebrovascular disease; upper respiratory infection; lower respiratory infection; bronchitis; rhinitis; nasopharyngitis; pharyngitis; sinusitis; allergic; chronic lower respiratory disease; emphysema; chronic obstructive pulmonary disease (COPD); asthma; other respiratory disease; sunburn; rheumatoid arthritis; frostbite; effects of heat and light; heatstroke; sunstroke; hypothermia; chilblain; extreme weather induced injury.

Inclusion criteria (assess each):
1. The literature mentions any of the 42 types of climate-sensitive communicable diseases listed above. Diseases not listed above should not be included.
2. Under the premise of satisfying “inclusion criterion 1”, the literature has discussed, analyzed, or researched climate-sensitive communicable diseases, including characteristics, diagnosis, pathology, epidemic patterns, treatment plans, costs, economic impacts, health policies, or health equity of these diseases.
3. The literature mentions any of the 47 types of climate-sensitive non-communicable diseases listed above. Diseases not listed above should not be included.
4. Under the premise of satisfying “inclusion criterion 3”, the literature has discussed, analyzed, or researched climate-sensitive non-communicable diseases, including characteristics, diagnosis, pathology, epidemic patterns, treatment plans, costs, economic impacts, health policies, or health equity of these diseases.

Exclusion criteria (assess each):
1. The literature does not mention any of the climate-sensitive diseases listed above.
2. The literature mentions some of climate-sensitive diseases listed above, but there has been no discussion, analysis, or research on these diseases, including their characteristics, diagnosis, pathology, epidemic patterns, treatment plans, costs, economic impacts, health policies, or health equity, etc.
3. The abstract and title of the literature are too brief or vague, lacking sufficient disease-related words or sentences to make judgements.

Output requirements:
1. For each inclusion and exclusion criterion, output one of “satisfied”, “not satisfied”, or “unclear”.
2. Finally, provide the final decision on whether to include the literature. If the literature meets someone of the “inclusion criterion 2” or “inclusion criterion 4” and does not meet any exclusion criteria, output “included”; If the literature meets any of the exclusion criteria, output “excluded”; If the literature only meets “inclusion criterion 1” or “inclusion criterion 3” and does not meet “inclusion criterion 2” or “inclusion criterion 4”, or if the information is limited and unclear, output “unclear”.

Format output of these criteria as JSON. Use this exact structure, even if output is “unclear”:
{Inclusion1 ..., Inclusion2 ..., Inclusion3 ..., Inclusion4 ..., Exclusion1 ..., Exclusion2 ..., Exclusion3 ..., Final_decision ...}
For example:
```json
{
“Inclusion1”: “satisfied”,
“Inclusion2”: “not satisfied”,
“Inclusion3”: “satisfied”,
“Inclusion4”: “satisfied”,
“Exclusion1”: “not satisfied”,
“Exclusion2”: “not satisfied”,
“Exclusion3”: “not satisfied”,
“Final_decision”: “included”
}
```
ABSTRACT: %s",substr(Abstract,1,3000))
  
response<-POST(
  "https://api.deepseek.com/v1/chat/completions",
  add_headers(Authorization=paste("Bearer",api_key)),
  content_type("application/json"),
  body=toJSON(list(
    model="deepseek-chat",
    messages=list(list(role="user",content=prompt)),
    temperature=0.5,  
    max_tokens=500
    ),auto_unbox=TRUE),
  timeout(30) 
)

status<-status_code(response)
raw_text<-content(response,"text",encoding="UTF-8") 
cat("==== START ====\n")
cat("DOI:",DOI,"\n")
cat("Status Code:",status,"\n")
cat("Raw Response Text:\n",raw_text,"\n")
cat("==== END ====\n\n")
if(status==200){
  parsed<-tryCatch({fromJSON(raw_text,simplifyVector=FALSE)},
                   error=function(e){
                     cat("JSON parsing failed\n")
                     return(NULL)
                     })
  if(!is.null(parsed) && !is.null(parsed$choices) && length(parsed$choices)>0){
    return(c(DOI=DOI,result=parsed$choices[[1]]$message$content))
    } else {
      return(c(DOI=DOI,result="MALFORMED_RESPONSE"))
    }
  } else {
    write(paste0(Sys.time()," | DOI=",DOI," | Status=",status,"\n",raw_text,"\n\n"),
          file=output_error,append=TRUE)
    return(c(DOI=DOI,result=paste0("API_ERROR_",status)))
  }
} 


#4.Batch processing function, used to automatically call the single article processing function in the previous section in small batches and intelligently save the results
process_abstracts<-function(data,api_key,batch_size=100,delay=1,save_every=200,initial_save_counter=1){
  total<-nrow(data)
  results<-list()
  save_counter<-initial_save_counter
  last_saved_index<-0 

for(i in seq(1,total,batch_size)){
  batch<-data[i:min(i+batch_size-1,total), ]

  batch_results<-map(seq_len(nrow(batch)),function(j){
    res<-NULL 
    attempt<-1
    while(is.null(res) && attempt<=3){
      res<-tryCatch({
        classify_abstract(batch$DOI[j],batch$Abstract[j],api_key)},
        error=function(e){
          Sys.sleep(1)
          NULL
        })
        attempt<-attempt+1
    }
    res %||% c(DOI=batch$DOI[j],result="FAILED_AFTER_RETRY")
  })

  results<-c(results,batch_results) 
  Sys.sleep(delay)
  temp_results<-bind_rows(results)
  write.csv(temp_results,output_temp,row.names=FALSE) 
   
  if((length(results)-last_saved_index)>=save_every || i+batch_size-1>=total){
    new_results<-results[(last_saved_index+1):length(results)]  
    batch_data<-bind_rows(new_results)
    batch_file<-sprintf(output_batch,save_counter)
    write.csv(batch_data,batch_file,row.names=FALSE)  
    cat(sprintf("Saving %s(Add %d pieces)\n",batch_file,nrow(batch_data)))
    last_saved_index<-length(results)
    save_counter<-save_counter+1 
  }

  cat(sprintf("Processed %d/%d (%.1f%%)...\n", 
              min(i+batch_size-1,total),total, 
              200*min(i+batch_size-1,total)/total))
}
  bind_rows(results)  
} 


#5.Execute processing, formally call the first two functions for screening, and ensure data coherence
completed_path<-file.path(Path,"Result/temp_results.csv") 
if(file.exists(completed_path)){
  completed_results<-read.csv(completed_path,stringsAsFactors=FALSE)
  completed_dois<-completed_results$DOI
  cat(sprintf("%d records completed, and will skip \n",length(completed_dois)))
} else {
  completed_results<-data.frame()
  completed_dois<-character(0)
  cat("Completed records not found, will process from the beginning \n")
}

remaining_data<-data[!data$DOI %in% completed_dois, ] 
initial_save_counter<-ceiling(nrow(completed_results)/200)+1

results<-process_abstracts(
  data=remaining_data,
  api_key=api_key,
  batch_size=100,   
  delay=1.5,
  initial_save_counter=initial_save_counter  
)

output_path<-file.path(Path,"Result/")
all_files<-list.files(path=output_path,pattern="^results_batch_\\d+\\.csv$",full.names=TRUE)  
all_data<-bind_rows(lapply(all_files,read.csv))   


#6.Parse and screen results
all_data_cleaned<-all_data %>%
  mutate(
    result_clean=str_remove_all(result,"^```json\\s*|\\s*```$"),
    result_clean=str_trim(result_clean)
  )
json_results<-map(all_data_cleaned$result_clean,~{
  tryCatch(fromJSON(.x),error=function(e)
    NULL)
})   
final_df<-map_dfr(seq_along(json_results),function(i){
  doi<-all_data_cleaned$DOI[i]
  result<-json_results[[i]]
  if(is.null(result)){
    data.frame(
      DOI=doi,
      Inclusion1=NA,
      Inclusion2=NA,
      Inclusion3=NA,
      Inclusion4=NA,
      Exclusion1=NA,
      Exclusion2=NA,
      Exclusion3=NA,
      Final_decision="FAILED_TO_PARSE", 
      stringsAsFactors=FALSE
    )
  } else {
    cbind(DOI=doi,as.data.frame(result))
  }
})  

output_path<-file.path(Path,"Result/parsed_results_clean_1st_step.csv")
write_csv(final_df,output_path)

included_data<-final_df %>% filter(Final_decision %in% c("included"))%>%
  left_join(combined_final,by="DOI")
unclear_data<-final_df %>% filter(Final_decision %in% c("unclear"))%>%
  left_join(combined_final,by="DOI")
unclear_full<-unclear_data 
output_path<-file.path(Path,"Output/included_only_1st_step.csv")
write.csv(included_data,output_path,row.names=FALSE)
output_path<-file.path(Path,"Output/unclear_only_1st_step.csv")
write.csv(unclear_data,output_path,row.names=FALSE)